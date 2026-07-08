from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any
import zipfile

import gradio as gr
import pandas as pd
import torch

from src.dental_detection.assistant import (
    APP_HOME,
    AiSettings,
    CONFIG_PATH,
    SAFETY_NOTICE,
    case_dir,
    default_advice,
    detection_prompt,
    ensure_app_dirs,
    export_dir,
    load_settings,
    normalize_base_url,
    report_dir,
    save_conversation,
    save_settings,
    test_chat_completion,
    chat_completion,
    DEFAULT_AI_PROMPT,
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_KEY_ENV,
    DEFAULT_AI_MODEL,
)
from src.dental_detection.case_store import (
    export_case_report,
    list_case_records,
    load_case_record as load_case_record_data,
    move_case_to_trash,
    search_case_records,
)
from src.dental_detection.config import DEFAULT_MODEL_PATH, MODEL_REGISTRY, PROJECT_ROOT
from src.dental_detection.batch_summary import build_batch_summary
from src.dental_detection.batch_overview_view import batch_overview_csv_text, batch_overview_html
from src.dental_detection.history_store import (
    append_history_records,
    clear_history_records,
    delete_history_record,
    history_rows,
    load_history_record as load_history_record_data,
    update_history_report_paths,
)
from src.dental_detection.error_messages import friendly_error_message
from src.dental_detection.image_quality import assess_image_quality_detail, format_quality_text
from src.dental_detection.inference import Detection, run_inference
from src.dental_detection.model_info import (
    build_model_cards,
    format_model_info_markdown,
    legend_html,
    model_cards_html,
)
from src.dental_detection.model_files import (
    SUPPORTED_MODEL_DIR_SUFFIXES,
    SUPPORTED_MODEL_SUFFIXES,
    model_label_from_path,
    scan_model_files,
    supported_suffix_text,
)
from src.dental_detection.reporting import SingleReportData, export_batch_docx_report, export_single_docx_report
from src.dental_detection.record_formatters import format_case_record, format_history_record
from src.dental_detection.record_views import (
    CASE_TABLE_COLUMNS,
    HISTORY_TABLE_COLUMNS,
    case_choices_from_rows as _case_choices_from_rows,
    case_table as _case_table,
    history_choices_from_rows as _history_choices_from_rows,
    history_id as _history_id,
    history_table_from_rows as _history_table_from_rows,
)
from src.dental_detection.result_levels import enrich_detection_row, has_detection_payload, iter_detection_items
from src.dental_detection.result_items import (
    item_model_results,
    iter_model_result_items,
    model_result_detections,
    model_result_name,
    model_result_path,
)
from src.dental_detection.text_utils import csv_safe_row, json_safe_value, text_value
from src.dental_detection.visualization import crop_detection_regions, draw_detections_with_filter, save_png_image, save_result_image
from ultralytics import YOLO

MODEL_SOURCE = "YOLOv8m 原始结构"
TABLE_COLUMNS = ["class", "中文名称", "confidence", "关注等级", "图像区域", "置信度解释", "x1", "y1", "x2", "y2"]
CSS_PATH = PROJECT_ROOT / "assets" / "workbench.css"
JS_PATH = PROJECT_ROOT / "assets" / "workbench.js"
EXAMPLE_DIR = PROJECT_ROOT / "assets" / "examples" / "dental"
EXAMPLE_META_PATH = EXAMPLE_DIR / "示例图片说明.json"
STARTUP_STORAGE_ROOT = Path(load_settings().storage_dir).expanduser()
MODEL_MODE_SINGLE = "单模型"
MODEL_MODE_COMPARE = "对比模型"
COMMON_OUTPUT_QUALITY_INDEX = 12
_EXTRA_ALLOWED_FILE_ROOTS: set[Path] = set()


def _safe_existing_root(path: str | Path | None) -> Path | None:
    if not path:
        return None
    try:
        root = Path(path).expanduser().resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        return None
    try:
        if not root.exists():
            return None
        return root.parent if root.is_file() else root
    except OSError:
        return None


def _load_workbench_css() -> str:
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return ""


def _load_workbench_js() -> str:
    if JS_PATH.exists():
        return JS_PATH.read_text(encoding="utf-8")
    return ""


def _workbench_theme():
    return gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="orange",
        neutral_hue="slate",
    )


def _allowed_file_roots() -> list[Path]:
    # 动态读取当前设置中的 storage_dir，确保更换存储目录后导出下载入口仍然可用
    try:
        current_storage = _safe_existing_root(load_settings().storage_dir)
    except Exception:
        current_storage = None
    roots = [
        APP_HOME,
        STARTUP_STORAGE_ROOT,
        PROJECT_ROOT / "outputs",
        *_EXTRA_ALLOWED_FILE_ROOTS,
    ]
    if current_storage:
        roots.append(current_storage)
    resolved: list[Path] = []
    for root in roots:
        path = _safe_existing_root(root)
        if path and path not in resolved:
            resolved.append(path)
    return resolved


def _sync_gradio_allowed_paths() -> None:
    """Refresh the running Gradio app's static-file allowlist after storage changes."""
    try:
        from gradio.context import LocalContext
    except Exception:
        return
    blocks = LocalContext.blocks.get(None)
    if blocks is None:
        return
    try:
        blocks.allowed_paths = [str(root) for root in _allowed_file_roots()]
    except Exception:
        return


def _remember_allowed_file_root(path: str | Path | None) -> None:
    root = _safe_existing_root(path)
    if root is not None:
        _EXTRA_ALLOWED_FILE_ROOTS.add(root)
        _sync_gradio_allowed_paths()


def _ensure_storage_root(storage_dir: str | None, context: str = "存储目录不可用") -> Path:
    try:
        root = ensure_app_dirs(storage_dir)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise _friendly_gr_error(exc, context) from exc
    _remember_allowed_file_root(root)
    return root


def _can_return_file(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        target = Path(path).expanduser().resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        return False
    if not target.is_file():
        return False
    return any(target == root or root in target.parents for root in _allowed_file_roots())


def _file_output(path: str | Path | None) -> str | None:
    return str(path) if _can_return_file(path) else None


def _file_component_output(path: str | Path | None):
    file_path = _file_output(path)
    return gr.update(value=file_path, visible=bool(file_path))


def _path_text(path: Any) -> str:
    return str(path or "") if path else ""


def _clear_file_output():
    return gr.update(value=None, visible=False)


def _empty_table(message: str = "暂无检测结果") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "class": message,
                "中文名称": "",
                "confidence": "",
                "关注等级": "",
                "图像区域": "",
                "置信度解释": "",
                "x1": "",
                "y1": "",
                "x2": "",
                "y2": "",
            }
        ],
        columns=TABLE_COLUMNS,
    )


def _table_from_detections(detections: list[Detection]) -> pd.DataFrame:
    rows = _clean_detection_records((det.as_row() for det in detections), image_size=None)
    return pd.DataFrame(rows, columns=TABLE_COLUMNS) if rows else _empty_table()


def _table_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = _clean_detection_records(records)
    return pd.DataFrame(rows, columns=TABLE_COLUMNS) if rows else _empty_table()


def _records_from_detections(detections: list[Detection], image_size: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    return _clean_detection_records((det.as_row() for det in detections), image_size=image_size)


def _clean_detection_records(detections: Any, image_size: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for det in iter_detection_items(detections):
        if not has_detection_payload(det):
            continue
        row = enrich_detection_row(det, image_size)
        if all(value in {"", None} for value in row.values()):
            continue
        rows.append(json_safe_value(row))
    return rows


def assess_image_quality(image) -> str:
    if image is None:
        return "等待上传图像"
    try:
        return format_quality_text(assess_image_quality_detail(image))
    except Exception as exc:
        return f"图像质量提示：质量评估失败，请确认图像格式是否正常。\n错误信息：{exc}"


def _result_visual_outputs(result: dict[str, Any] | None) -> tuple[Any, list[tuple[Any, str]], str]:
    if not isinstance(result, dict):
        return None, [], "暂无疑似区域局部图"
    annotated = result.get("annotated")
    original = result.get("original")
    detections = _clean_detection_records(result.get("_visible_detections", model_result_detections(result)))
    regions = crop_detection_regions(original, detections)
    gallery = [(item["image"], item["caption"]) for item in regions]
    status = f"已生成 {len(gallery)} 个疑似区域局部图" if gallery else "暂无疑似区域局部图"
    return annotated, gallery, status


def _quality_payload(image) -> tuple[str, str]:
    if image is None:
        return "等待上传图像", "未知"
    try:
        detail = assess_image_quality_detail(image)
        return format_quality_text(detail), detail.quality_level
    except Exception as exc:
        return f"图像质量提示：质量评估失败，请确认图像格式是否正常。\n错误信息：{exc}", "未知"


def _device_choices() -> list[tuple[str, str]]:
    choices = [("CPU", "cpu")]
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        if count <= 1:
            choices.append(("CUDA GPU", "cuda:0"))
        else:
            choices.extend((f"CUDA GPU {index}", f"cuda:{index}") for index in range(count))
    return choices


def _default_device_choice() -> str:
    choices = _device_choices()
    return choices[1][1] if len(choices) > 1 else "cpu"


def _device(device_choice: str) -> tuple[str | int, bool]:
    cuda_available = torch.cuda.is_available()
    choice = str(device_choice or "cpu").strip().lower()
    if choice.startswith("cuda") and not cuda_available:
        raise _friendly_gr_error("CUDA not available", "推理设备不可用")
    if choice.startswith("cuda"):
        try:
            index = int(choice.split(":", 1)[1]) if ":" in choice else 0
        except (IndexError, ValueError):
            raise _friendly_gr_error(f"invalid CUDA device: {device_choice}", "推理设备不可用") from None
        if index < 0 or index >= torch.cuda.device_count():
            raise _friendly_gr_error(
                f"invalid CUDA device index: {device_choice}; available count: {torch.cuda.device_count()}",
                "推理设备不可用",
            )
        return index, cuda_available
    if choice != "cpu":
        return "cpu", cuda_available
    return "cpu", cuda_available


def _device_label(device: str | int) -> str:
    return f"cuda:{device}" if isinstance(device, int) else "cpu"


def _detect_model(model_name: str, image, use_clahe: bool, conf: float, iou: float, device):
    model_info = MODEL_REGISTRY[model_name]
    return _detect_model_path(model_name, model_info["path"], image, use_clahe, conf, iou, device)


def _class_name_mapping(names: Any) -> dict[str, Any]:
    if isinstance(names, dict):
        return {str(key): value for key, value in names.items()}
    if isinstance(names, (list, tuple)):
        return {str(index): value for index, value in enumerate(names)}
    return {}


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    return max(minimum, min(maximum, number))


def _detect_model_path(model_name: str, model_path: str | Path, image, use_clahe: bool, conf: float, iou: float, device):
    model_path = Path(model_path)
    _validate_model_artifact(model_path, model_name)
    conf = _bounded_float(conf, default=0.25, minimum=0.01, maximum=0.99)
    iou = _bounded_float(iou, default=0.7, minimum=0.01, maximum=0.99)
    try:
        original, model_input, annotated, detections, names = run_inference(
            image=image,
            model_path=model_path,
            use_clahe=use_clahe,
            conf=conf,
            iou=iou,
            imgsz=1280,
            device=device,
        )
    except Exception as exc:
        raise _friendly_gr_error(exc, "推理失败") from exc
    records = _records_from_detections(detections, model_input.size)
    return {
        "model": model_name,
        "original": original,
        "model_input": model_input,
        "annotated": annotated,
        "full_annotated": annotated,
        "detections": records,
        "table": _table_from_records(records),
        "class_names": _class_name_mapping(names),
        "model_path": str(Path(model_path).resolve()),
    }


def _model_path_or_default(path: str, fallback: str) -> str:
    value = str(path or "").strip()
    try:
        return str(Path(value).expanduser().resolve()) if value else str(Path(fallback).resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise _friendly_gr_error(exc, "模型路径无效") from exc


def _model_dir_or_default(path: str | Path | None) -> str:
    try:
        target = Path(path or PROJECT_ROOT / "models").expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return str((PROJECT_ROOT / "models").resolve())
    return str(target.parent if target.is_file() else target)


def _configured_models(model_mode: str, primary_model_path: str, compare_model_path: str) -> list[tuple[str, Path]]:
    primary = Path(_model_path_or_default(primary_model_path, str(DEFAULT_MODEL_PATH)))
    models = [(model_label_from_path(primary), primary)]
    if model_mode == MODEL_MODE_COMPARE:
        compare = Path(_model_path_or_default(compare_model_path, str(MODEL_REGISTRY[MODEL_SOURCE]["path"])))
        if primary == compare:
            raise gr.Error("对比模型不能与主模型使用同一个权重文件，请选择另一个模型后再运行对比。")
        models.append((model_label_from_path(compare), compare))
    return models


def _validate_compare_model_selection(model_mode: str, primary_model_path: str, compare_model_path: str) -> None:
    _configured_models(model_mode, primary_model_path, compare_model_path)


def _is_supported_model_artifact(path: Path) -> bool:
    suffix = path.suffix.lower()
    if path.is_file():
        return suffix in SUPPORTED_MODEL_SUFFIXES
    if path.is_dir():
        return suffix in SUPPORTED_MODEL_DIR_SUFFIXES
    return False


def _validate_model_artifact(path: Path, role: str = "模型") -> None:
    if not path.exists():
        raise _friendly_gr_error(f"{role}: model file not found: {path}", "模型文件不存在")
    supported_suffixes = SUPPORTED_MODEL_SUFFIXES | SUPPORTED_MODEL_DIR_SUFFIXES
    if path.suffix.lower() not in supported_suffixes:
        raise _friendly_gr_error(
            f"{role}: unsupported model format {path.suffix}; supported: {', '.join(sorted(supported_suffixes))}",
            "模型文件格式不支持",
        )
    if not _is_supported_model_artifact(path):
        raise _friendly_gr_error(
            f"{role}: model path is not a file or supported model package: {path}",
            "模型路径无效",
        )


def _validate_model_files(models: list[tuple[str, Path]]) -> None:
    for role, path in models:
        _validate_model_artifact(path, role)


def refresh_model_choices(model_dir: str, current_value: str | None = None):
    choices = scan_model_files(model_dir)
    # 保留用户已选模型，仅当原模型不在新列表中时才回退第一个
    value = current_value
    if value and not any(value == c[1] for c in choices):
        value = choices[0][1] if choices else None
    if not value:
        value = choices[0][1] if choices else None
    suffixes = supported_suffix_text()
    message = f"已扫描到 {len(choices)} 个模型文件。" if choices else f"当前目录未发现支持的模型文件（{suffixes}），请确认路径。"
    return gr.update(choices=choices, value=value), message


def apply_selected_model(selected_path: str, target: str):
    if not selected_path:
        raise gr.Error("请先从模型文件下拉框选择一个支持的模型文件。")
    try:
        model_path = Path(selected_path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise _friendly_gr_error(exc, "模型路径无效") from exc
    _validate_model_artifact(model_path)
    path = str(model_path)
    if target == "对比模型":
        return gr.update(), gr.update(value=path), gr.update(), gr.update(), f"已填入对比模型：{path}"
    return (
        gr.update(value=path),
        gr.update(),
        model_cards_html(_model_cards(path), path),
        _current_model_info_markdown(path),
        f"已填入主模型：{path}",
    )


def _model_cards(selected_path: str | None = None) -> list[dict[str, Any]]:
    return build_model_cards(MODEL_REGISTRY)


def _model_card_choices() -> list[tuple[str, str]]:
    choices = []
    for card in _model_cards():
        suffix = "可用" if card.get("available") else "缺失"
        choices.append((f"{card['title']} - {card['name']}（{suffix}）", card["path"]))
    return choices


def _current_model_info_markdown(selected_path: str | None = None) -> str:
    cards = _model_cards(selected_path)
    selected = next((card for card in cards if str(card.get("path")) == str(selected_path or "")), None)
    if selected:
        return format_model_info_markdown(selected)
    if selected_path:
        try:
            path = Path(selected_path).expanduser()
        except (OSError, RuntimeError, ValueError):
            path = Path("invalid_model_path")
            available = False
        else:
            available = _is_supported_model_artifact(path)
        return format_model_info_markdown(
            {
                "name": model_label_from_path(path),
                "architecture": "自定义 YOLO 模型",
                "role": "用户选择的模型文件",
                "path": str(path),
                "available": available,
                "metrics": {},
            }
        )
    return format_model_info_markdown(cards[0])


def apply_model_card(selected_path: str, model_dir: str | None = None):
    if not selected_path:
        raise gr.Error("请先选择一个模型卡片。")
    card = next((item for item in _model_cards() if item.get("path") == selected_path), None)
    if not card:
        raise gr.Error("所选模型卡片无效，请刷新页面后重试。")
    if not card.get("available"):
        raise _friendly_gr_error(f"model file not found: {card.get('path')}", "模型文件不存在")
    path = str(Path(card["path"]).expanduser().resolve())
    choices = scan_model_files(_model_dir_or_default(model_dir))
    if not any(path == value for _, value in choices):
        choices = [(f"{model_label_from_path(path)}  |  {path}", path), *choices]
    return (
        gr.update(value=path),
        gr.update(choices=choices, value=path),
        model_cards_html(_model_cards(path), path),
        _current_model_info_markdown(path),
        f"已选择{card['title']}：{card['name']}",
    )


def _choose_directory_dialog(title: str, initial_dir: str | Path) -> str | None:
    """Open a native directory picker when the app is running with a desktop session."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise gr.Error(f"当前 Python 环境无法打开路径选择器：{exc}") from exc

    start_dir = Path(initial_dir or PROJECT_ROOT).expanduser()
    if not start_dir.exists():
        start_dir = start_dir.parent if start_dir.parent.exists() else PROJECT_ROOT
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title=title,
            initialdir=str(start_dir.resolve()),
            mustexist=True,
        )
    except Exception as exc:
        raise gr.Error(f"无法打开路径选择器，请手动输入路径：{exc}") from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
    return selected or None


def choose_model_dir(model_dir: str, current_value: str | None = None):
    selected = _choose_directory_dialog("选择模型目录", model_dir or PROJECT_ROOT / "models")
    if not selected:
        return gr.update(), gr.update(), "未选择模型目录。"
    root = _safe_existing_root(selected)
    if root is None:
        return gr.update(), gr.update(), "选择的模型目录不可访问，请手动检查路径后重试。"
    path = str(root)
    choices = scan_model_files(path)
    value = current_value if current_value and any(current_value == c[1] for c in choices) else None
    value = value or (choices[0][1] if choices else None)
    suffixes = supported_suffix_text()
    message = f"已选择模型目录：{path}。扫描到 {len(choices)} 个模型文件。"
    if not choices:
        message += f" 请确认该目录或其子目录中存在支持的模型文件（{suffixes}）。"
    return gr.update(value=path), gr.update(choices=choices, value=value), message


def test_model_file(primary_model_path: str, compare_model_path: str, model_mode: str):
    messages = []
    try:
        models = _configured_models(model_mode, primary_model_path, compare_model_path)
    except gr.Error as exc:
        return str(exc)
    except Exception as exc:
        return friendly_error_message(exc, "模型路径无效")
    for role, path in models:
        if not path.exists():
            messages.append(f"{role}：文件不存在，路径为 {path}")
            continue
        supported_suffixes = SUPPORTED_MODEL_SUFFIXES | SUPPORTED_MODEL_DIR_SUFFIXES
        if path.suffix.lower() not in supported_suffixes:
            messages.append(f"{role}：文件后缀不在支持列表中，当前路径为 {path}")
            continue
        if not _is_supported_model_artifact(path):
            messages.append(f"{role}：路径不是可加载的模型文件或支持的模型包，当前路径为 {path}")
            continue
        try:
            model = YOLO(str(path))
            names = getattr(model, "names", {})
            class_text = ", ".join(str(value) for value in names.values()) if isinstance(names, dict) else str(names)
            messages.append(f"{role}：可加载。类别：{class_text or '未读取到类别名'}")
        except Exception as exc:
            messages.append(f"{role}：加载失败：{exc}")
    return "\n".join(messages)


def _ai_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str = "简洁版",
) -> AiSettings:
    if key_mode == "环境变量":
        api_key = (env_api_key or "").strip() or DEFAULT_AI_KEY_ENV
    else:
        api_key = direct_api_key_visible if direct_key_visible else direct_api_key_hidden
    return AiSettings(
        enabled=ai_enabled,
        base_url=normalize_base_url(base_url),
        model=(ai_model or "").strip() or DEFAULT_AI_MODEL,
        key_mode=key_mode,
        api_key=(api_key or "").strip(),
        save_api_key=save_key,
        auto_save=auto_save,
        storage_dir=(storage_dir or "").strip() or str(APP_HOME),
        custom_prompt=(custom_prompt or "").strip() or DEFAULT_AI_PROMPT,
        advice_style=advice_style if advice_style in {"简洁版", "医生版", "患者版"} else "简洁版",
    )


def _save_runtime_settings(
    settings: AiSettings,
    model_mode: str | None = None,
    model_dir: str | None = None,
    primary_model_path: str | None = None,
    compare_model_path: str | None = None,
    persist_storage: bool = False,
) -> Path:
    saved = load_settings()
    if not persist_storage:
        # 检测、测试接口等运行时动作可以使用界面上的临时 storage_dir，
        # 但不应静默迁移或覆盖用户已保存的数据根目录。
        settings.storage_dir = saved.storage_dir
    settings.enable_compare = saved.enable_compare
    settings.show_summary = saved.show_summary
    settings.save_history = saved.save_history
    settings.history_limit = saved.history_limit
    settings.model_mode = (model_mode or saved.model_mode) if settings.enable_compare else MODEL_MODE_SINGLE
    settings.model_dir = _model_dir_or_default(model_dir or saved.model_dir)
    settings.primary_model_path = _model_path_or_default(
        primary_model_path or saved.primary_model_path,
        str(DEFAULT_MODEL_PATH),
    )
    settings.compare_model_path = _model_path_or_default(
        compare_model_path or saved.compare_model_path,
        str(MODEL_REGISTRY[MODEL_SOURCE]["path"]),
    )
    return save_settings(settings, migrate_data=persist_storage)


def _api_key_inputs(saved: AiSettings) -> tuple[str, str]:
    if saved.key_mode == "环境变量":
        return saved.api_key or DEFAULT_AI_KEY_ENV, ""
    return DEFAULT_AI_KEY_ENV, saved.api_key if saved.save_api_key else ""


def _build_advice(settings: AiSettings, detections: list[dict[str, Any]]) -> str:
    if not settings.enabled:
        return default_advice(detections)
    style_prompt = _advice_style_prompt(settings.advice_style)
    prompt = settings.custom_prompt
    if style_prompt:
        prompt = f"{prompt}\n{style_prompt}"
    try:
        return chat_completion(
            settings,
            detection_prompt(detections, prompt),
            temperature=0.2,
            max_tokens=500,
        )
    except Exception as exc:
        return f"{default_advice(detections)}\n\n{friendly_error_message(exc, 'AI 建议生成失败')}"


def _advice_style_prompt(style: str) -> str:
    return {
        "简洁版": "建议风格：简洁版，重点明确，避免冗长。",
        "医生版": "建议风格：医生版，保留类别名、置信度和必要的检测框信息，语言专业克制。",
        "患者版": "建议风格：患者版，使用易懂中文，少用技术术语，避免制造焦虑。",
    }.get(style, "")


def _normalize_history_limit(value: Any) -> int:
    try:
        return max(1, min(1000, int(value or 100)))
    except (TypeError, ValueError):
        return 100


def _conversation_from_advice(advice: str) -> list[dict[str, str]]:
    return [{"role": "assistant", "content": advice}]


def _auto_save_conversation(history: list[dict[str, str]], storage_dir: str) -> str:
    try:
        save_conversation(history, storage_dir)
    except Exception as exc:
        message = friendly_error_message(exc, "自动保存对话失败")
        return f"自动保存对话失败，检测或回复结果已保留。\n{message}"
    return ""


def _auto_append_history(batch_state: list[dict[str, Any]], storage_dir: str, history_limit: int | float) -> str:
    try:
        append_history_records(batch_state, storage_dir, _normalize_history_limit(history_limit))
    except Exception as exc:
        message = friendly_error_message(exc, "自动保存检测历史失败")
        return f"自动保存检测历史失败，检测结果已保留。\n{message}"
    return ""


def _normalize_chat_history(history: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in history or []:
        if isinstance(item, dict):
            role = str(item.get("role") or "assistant")
            content = item.get("content", "")
            if role not in {"system", "user", "assistant"}:
                role = "assistant"
            normalized.append({"role": role, "content": str(content)})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            user_content, assistant_content = item[0], item[1]
            if user_content is not None and user_content != "":
                normalized.append({"role": "user", "content": str(user_content)})
            if assistant_content is not None and assistant_content != "":
                normalized.append({"role": "assistant", "content": str(assistant_content)})
        elif item is not None and item != "":
            normalized.append({"role": "assistant", "content": str(item)})
    return normalized


def _suggestion_type(ai_enabled: bool) -> str:
    return "ai" if ai_enabled else "default"


def _safe_stem(name: str) -> str:
    stem = Path(name).stem or "image"
    # 保留 Unicode 字母/数字、空格、中文等非 ASCII 字符，只过滤路径分隔符和控制字符
    # Windows 禁用字符 < > : " / \\ | ? * 也被过滤
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" ._")
    if safe.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        safe = f"{safe}_file"
    safe = safe or "image"
    return safe[:120].rstrip(" ._") or "image"


def _matches_item_name(item: dict[str, Any], selected_name: Any) -> bool:
    selected_text = str(selected_name or "").strip()
    if not selected_text:
        return False
    return any(
        str(item.get(field) or "").strip() == selected_text
        for field in ("display_name", "name", "image_name")
    )


def _current_item(batch_state: list[dict[str, Any]], selected_name: str | None = None) -> dict[str, Any]:
    if not batch_state:
        raise gr.Error("当前没有可用的检测结果。")
    if selected_name:
        for item in batch_state:
            if _matches_item_name(item, selected_name):
                return item
        # 有选中名称但未匹配到任何项 → 抛出明确错误，不静默回退
        raise gr.Error("当前选择的结果已失效，请重新选择图片。")
    return batch_state[0]


def _case_detail_from_choice(choice: str | None, storage_dir: str) -> str:
    if not choice:
        return format_case_record(None)
    return load_case_record(choice, storage_dir)


def _case_file_name_from_choice(choice: str) -> str:
    file_name = str(choice or "").split("|")[-1].strip()
    if Path(file_name).name != file_name or not file_name.startswith("case_") or not file_name.endswith(".json"):
        raise gr.Error("病例选择无效，请刷新病例列表后重试。")
    return file_name


def _validate_case_date_filters(date_from: str, date_to: str) -> tuple[str, str]:
    start = str(date_from or "").strip()
    end = str(date_to or "").strip()
    for label, value in [("开始日期", start), ("结束日期", end)]:
        if not value:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise gr.Error(f"{label}格式应为 YYYY-MM-DD，例如 2026-06-10。") from None
    if start and end and start > end:
        raise gr.Error("开始日期不能晚于结束日期，请调整筛选条件。")
    return start, end


def _write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding=encoding)
    tmp_path.replace(path)


def _html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _toast(message: str, kind: str = "success") -> str:
    if not message:
        return ""
    return f'<div class="app-toast app-toast-{kind}">{_html_escape(message).replace(chr(10), "<br>")}</div>'


def _friendly_gr_error(exc: BaseException | str, context: str = "操作失败") -> gr.Error:
    return gr.Error(friendly_error_message(exc, context))


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _report_annotated_image(result: dict[str, Any]) -> Any:
    return _first_present(result.get("full_annotated"), result.get("annotated"))


def _visible_class_choices(result: dict[str, Any] | None) -> list[str]:
    detections = _clean_detection_records(model_result_detections(result or {}))
    choices: list[str] = []
    for row in detections:
        label = str(row.get("中文名称") or row.get("class") or "").strip()
        if label and label not in choices:
            choices.append(label)
    return choices


def _visible_class_update(result: dict[str, Any] | None):
    choices = _visible_class_choices(result)
    return gr.update(choices=choices, value=choices, interactive=bool(choices))


def _load_example_metadata() -> list[dict[str, Any]]:
    if not EXAMPLE_META_PATH.exists():
        return []
    try:
        data = json.loads(EXAMPLE_META_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        file_name = Path(str(item.get("文件名") or "")).name
        path = EXAMPLE_DIR / file_name
        if file_name and path.exists():
            items.append({**item, "path": path})
    return items


def _example_choices() -> list[tuple[str, str]]:
    choices = []
    for item in _load_example_metadata():
        name = str(item.get("示例名称") or item.get("文件名") or item["path"].name)
        expected = str(item.get("预期类别") or "").strip()
        label = f"{name} | {expected}" if expected else name
        choices.append((label, str(item["path"])))
    return choices


def _example_preview_text(path_text: str | None) -> str:
    if not path_text:
        return "选择示例后会在这里显示说明。"
    target = Path(path_text)
    for item in _load_example_metadata():
        if item["path"] == target:
            return "\n".join(
                [
                    f"示例名称：{item.get('示例名称', target.name)}",
                    f"预期类别：{item.get('预期类别', '未标注')}",
                    f"脱敏状态：{item.get('是否脱敏', '是')}",
                    str(item.get("说明文本") or ""),
                ]
            ).strip()
    return "未找到该示例说明。"


def load_demo_example(path_text: str | None):
    if not path_text:
        raise gr.Error("请先选择一张示例图片。")
    path = Path(path_text)
    try:
        in_example_dir = path.parent.resolve() == EXAMPLE_DIR.resolve()
        exists = path.exists()
    except (OSError, RuntimeError, ValueError) as exc:
        raise _friendly_gr_error(exc, "示例图片路径无效") from exc
    if not in_example_dir or not exists:
        raise gr.Error("示例图片不存在，请检查 assets/examples/dental 目录。")
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as img:
            image = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:
        raise _friendly_gr_error(exc, "示例图片无法读取") from exc
    return image, _example_preview_text(str(path))


def _detections_html(detections: list[dict[str, Any]]) -> str:
    detections = _clean_detection_records(detections)
    if not detections:
        return "<p>未检测到目标框。</p>"
    rows = []
    for det in detections:
        cells = "".join(
            f"<td>{_html_escape(det.get(key, ''))}</td>" for key in TABLE_COLUMNS
        )
        rows.append(f"<tr>{cells}</tr>")
    headers = "".join(f"<th>{name}</th>" for name in TABLE_COLUMNS)
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _model_detections_html(results: list[dict[str, Any]]) -> str:
    if len(results) <= 1:
        return _detections_html(model_result_detections(results[0]) if results else [])
    sections = []
    for result in results:
        model = _html_escape(model_result_name(result))
        detections = _clean_detection_records(model_result_detections(result))
        sections.append(f"<h3>{model}</h3>{_detections_html(detections)}")
    return "".join(sections)


def _model_result_images_html(model_items: list[dict[str, Any]]) -> str:
    image_items = []
    for item in model_items:
        model = _html_escape(model_result_name(item))
        image_files = item.get("image_files") if isinstance(item.get("image_files"), dict) else {}
        result_file = image_files.get("result") if image_files else ""
        if result_file:
            image_items.append(f'<figure><img src="{_html_escape(result_file)}"><figcaption>{model}</figcaption></figure>')
    if not image_items:
        return ""
    return '<div class="grid">' + "".join(image_items) + "</div>"


def _unique_report_paths(storage_dir: str, stamp: str) -> tuple[Path, Path]:
    base = report_dir(storage_dir)
    root = base / f"single_report_{stamp}"
    counter = 1
    while root.exists():
        root = base / f"single_report_{stamp}_{counter:02d}"
        counter += 1
    return root, root / f"{root.name}.zip"


def _item_results(item: dict[str, Any]) -> list[dict[str, Any]]:
    return item_model_results(item)


def _advice_detections(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        model_name = text_value(model_result_name(result), "unknown")
        for det in _clean_detection_records(model_result_detections(result)):
            rows.append({**det, "model": model_name, "模型": model_name})
    return rows


def _model_result_records(item: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in _item_results(item):
        model_name = text_value(model_result_name(result), "unknown")
        detections = []
        for det in _clean_detection_records(model_result_detections(result)):
            detections.append({**det, "模型": model_name})
        rows.append(
            {
                "model": model_name,
                "model_path": text_value(model_result_path(result)),
                "detection_count": len(detections),
                "detections": detections,
            }
        )
    return rows


def _report_match_key(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("display_name") or value.get("name") or value.get("image_name") or "").strip()
    return str(value or "").strip()


def _item_display_name(item: dict[str, Any], fallback: str = "") -> str:
    return str(item.get("display_name") or item.get("name") or item.get("image_name") or fallback).strip()


def _summary_model_name(summary_data: dict[str, Any]) -> str:
    model_results = summary_data.get("模型结果")
    for result in iter_model_result_items(model_results):
        model_name = model_result_name(result, "")
        if model_name:
            return model_name
    return text_value(summary_data.get("模型"))


def _sync_report_path(batch_state: list[dict[str, Any]], image_refs: list[Any], path: str | Path, field: str) -> None:
    exact_ref_ids = {id(ref) for ref in image_refs if isinstance(ref, dict)}
    match_keys = {_report_match_key(ref) for ref in image_refs if not isinstance(ref, dict) and _report_match_key(ref)}
    if not exact_ref_ids and not match_keys:
        return
    path_text = str(path)
    for item in batch_state or []:
        if id(item) in exact_ref_ids or _report_match_key(item) in match_keys:
            item[field] = path_text
            item["report_path"] = path_text


def _summary_lines(batch_state: list[dict[str, Any]], export_info: dict[str, Any]) -> list[str]:
    class_counts: Counter[str] = Counter()
    total_boxes = 0
    model_counts: Counter[str] = Counter()
    for item in batch_state:
        for result in _item_results(item):
            detections = _clean_detection_records(model_result_detections(result))
            total_boxes += len(detections)
            model_counts.update([model_result_name(result)])
            class_counts.update(str(det.get("class", "unknown")) for det in detections)

    lines = [
        "YOLO Dental Lesion Detection Batch Export",
        f"导出时间: {export_info['exported_at']}",
        f"图片总数: {export_info.get('image_count', len(batch_state))}",
        f"成功处理: {export_info.get('success_count', len(batch_state))}",
        f"处理失败: {export_info.get('failed_count', 0)}",
        f"检测到的总框数: {total_boxes}",
        f"是否使用 CLAHE: {export_info['use_clahe']}",
        f"conf: {export_info['conf']}",
        f"iou: {export_info['iou']}",
        f"models: {', '.join(export_info.get('models') or [export_info.get('model', 'unknown')])}",
        f"模型结果组数: {sum(model_counts.values())}",
        "",
        "各类别数量:",
    ]
    if class_counts:
        lines.extend(f"- {name}: {count}" for name, count in sorted(class_counts.items()))
    else:
        lines.append("- 无检测框")
    lines.extend(["", "各模型处理数量:"])
    if model_counts:
        lines.extend(f"- {name}: {count}" for name, count in sorted(model_counts.items()))
    else:
        lines.append("- 无模型结果")
    return lines


def _unique_batch_export_paths(storage_dir: str, stamp: str) -> tuple[Path, Path]:
    export_base = export_dir(storage_dir)
    export_root = export_base / f"batch_result_{stamp}"
    counter = 1
    while export_root.exists():
        export_root = export_base / f"batch_result_{stamp}_{counter:02d}"
        counter += 1
    zip_path = export_root / f"{export_root.name}.zip"
    return export_root, zip_path


def _unique_case_path(storage_dir: str, stamp: str, safe_case: str) -> Path:
    base = case_dir(storage_dir)
    path = base / f"case_{stamp}_{safe_case}.json"
    counter = 1
    while path.exists():
        path = base / f"case_{stamp}_{safe_case}_{counter:02d}.json"
        counter += 1
    return path


def export_batch_results(batch_state: list[dict[str, Any]], storage_dir: str):
    if not batch_state:
        raise gr.Error("请先完成批量检测，再导出结果。")

    batch_errors = batch_state[0].get("batch_errors", []) if batch_state else []
    if not isinstance(batch_errors, list):
        batch_errors = []
    batch_overview = build_batch_summary(batch_state, batch_errors)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _ensure_storage_root(storage_dir)
    export_root, zip_path = _unique_batch_export_paths(storage_dir, stamp)
    export_root.mkdir(parents=True, exist_ok=True)
    work_dir = export_root / "payload"
    images_dir = work_dir / "images"
    suggestions_dir = work_dir / "suggestions"
    images_dir.mkdir(parents=True, exist_ok=True)
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    first_summary = batch_state[0].get("summary", {})
    first_summary = first_summary if isinstance(first_summary, dict) else {}
    first_model_results = list(iter_model_result_items(first_summary.get("模型结果"))) if isinstance(first_summary, dict) else []
    model_names = [
        model_result_name(item, "")
        for item in first_model_results
        if model_result_name(item, "")
    ]
    if not model_names and batch_state:
        model_names = [
            model_result_name(result, "")
            for result in _item_results(batch_state[0])
            if model_result_name(result, "")
        ]
    export_info = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "image_count": batch_overview.get("图片总数", len(batch_state)),
        "success_count": batch_overview.get("成功处理", len(batch_state)),
        "failed_count": batch_overview.get("处理失败", 0),
        "use_clahe": bool(first_summary.get("CLAHE增强", False)),
        "conf": first_summary.get("conf", "unknown"),
        "iou": first_summary.get("iou", "unknown"),
        "model": model_names[0] if model_names else first_summary.get("模型", "unknown"),
        "models": model_names or [first_summary.get("模型", "unknown")],
        "model_mode": first_summary.get("模型模式", MODEL_MODE_SINGLE),
    }
    try:
        csv_rows: list[dict[str, Any]] = []
        json_items = []

        for index, item in enumerate(batch_state, start=1):
            name = item.get("name") or item.get("image_name") or f"image_{index:03d}.png"
            display_name = _item_display_name(item, str(name))
            stem = f"{index:03d}_{_safe_stem(name)}"
            result = item.get("result") or item
            all_results = _item_results(item)
            primary_detections = _clean_detection_records(model_result_detections(result))
            suggestion_type = item.get("suggestion_type", "default")
            advice = item.get("advice") or item.get("suggestion") or ""

            original_image = _first_present(result.get("original"), result.get("original_image"))
            input_image = _first_present(result.get("model_input"), result.get("input_image"))
            annotated_image = _first_present(_report_annotated_image(result), result.get("result_image"))
            if original_image is None or input_image is None or annotated_image is None:
                raise gr.Error(f"{name} 的批量结果不完整，无法导出图片。")

            save_png_image(original_image, images_dir / f"{stem}_original.png")
            save_png_image(input_image, images_dir / f"{stem}_input.png")
            save_png_image(annotated_image, images_dir / f"{stem}_result.png")
            _write_text(suggestions_dir / f"{stem}.txt", advice)

            model_json_items = []
            for model_index, model_result in enumerate(all_results, start=1):
                model_name = model_result_name(model_result, text_value(item.get("model"), "unknown"))
                detections = _clean_detection_records(model_result_detections(model_result))
                model_image_files = {}
                model_annotated = _report_annotated_image(model_result)
                if model_annotated is not None:
                    model_result_file = f"images/{stem}_model_{model_index:02d}_{_safe_stem(model_name)}_result.png"
                    save_png_image(model_annotated, work_dir / model_result_file)
                    model_image_files["result"] = model_result_file
                model_json_items.append(
                    {
                        "model": model_name,
                        "model_path": model_result_path(model_result),
                        "detections": detections,
                        "image_files": model_image_files,
                    }
                )
                if detections:
                    for det in detections:
                        csv_rows.append(
                            {
                                "image_name": name,
                                "display_name": display_name,
                                "model": model_name,
                                **{key: det.get(key, "") for key in TABLE_COLUMNS},
                                "suggestion_type": suggestion_type,
                            }
                        )
                else:
                    csv_rows.append(
                        {
                            "image_name": name,
                            "display_name": display_name,
                            "model": model_name,
                            **{key: "" for key in TABLE_COLUMNS},
                            "suggestion_type": suggestion_type,
                        }
                    )

            json_items.append(
                {
                    "image_name": name,
                    "display_name": display_name,
                    "model": model_result_name(result, text_value(item.get("model"), "unknown")),
                    "models": model_json_items,
                    "suggestion_type": suggestion_type,
                    "suggestion": advice,
                    "quality_text": item.get("quality_text", ""),
                    "quality_level": item.get("quality_level", ""),
                    "detections": primary_detections,
                    "image_files": {
                        "original": f"images/{stem}_original.png",
                        "input": f"images/{stem}_input.png",
                        "result": f"images/{stem}_result.png",
                    },
                }
            )

        csv_path = work_dir / "detections.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["image_name", "display_name", "model", *TABLE_COLUMNS, "suggestion_type"],
            )
            writer.writeheader()
            writer.writerows(csv_safe_row(row) for row in csv_rows)

        _write_text(
            work_dir / "detections.json",
            json.dumps(
                json_safe_value({"export": export_info, "overview": batch_overview, "items": json_items}),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
        )
        _write_text(
            work_dir / "batch_overview.json",
            json.dumps(json_safe_value(batch_overview), ensure_ascii=False, indent=2, allow_nan=False),
        )
        _write_text(
            work_dir / "批量检测总览.json",
            json.dumps(json_safe_value(batch_overview), ensure_ascii=False, indent=2, allow_nan=False),
        )
        _write_text(
            work_dir / "批量检测总览.csv",
            batch_overview_csv_text(batch_overview),
            encoding="utf-8-sig",
        )
        _write_text(
            work_dir / "批量检测总览.html",
            f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>批量检测总览</title>
  <style>
    body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 28px; color: #172033; }}
    .overview-stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .overview-stat {{ border: 1px solid #d7dde8; padding: 10px; border-radius: 6px; }}
    .overview-stat span {{ display: block; color: #5d6b82; font-size: 13px; }}
    .overview-stat strong {{ display: block; font-size: 20px; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 20px; }}
    th, td {{ border: 1px solid #d7dde8; padding: 8px; text-align: left; }}
    th {{ background: #eff4fb; }}
    .result-legend {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 12px 0 22px; }}
    .legend-item {{ border: 1px solid #d7dde8; border-radius: 6px; padding: 10px; }}
    .legend-swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 999px; margin-right: 6px; vertical-align: middle; }}
    .legend-item strong {{ margin-right: 6px; }}
    .legend-item span:last-child {{ display: block; color: #5d6b82; font-size: 13px; margin-top: 4px; line-height: 1.5; }}
  </style>
</head>
<body>
  <h1>批量检测总览</h1>
  <h2>图例与类别说明</h2>
  {legend_html()}
  {batch_overview_html(batch_overview)}
</body>
</html>
""",
        )
        with (work_dir / "class_stats.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["类别", "中文名称", "检测框数量", "涉及图片数", "平均置信度", "最高置信度"],
            )
            writer.writeheader()
            writer.writerows(csv_safe_row(row) for row in batch_overview.get("类别统计", []))
        with (work_dir / "focus_images.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["排名", "图片名称", "最高类别", "原始类别", "最高置信度", "检测框数量", "关注等级"])
            writer.writeheader()
            writer.writerows(csv_safe_row(row) for row in batch_overview.get("重点关注图片", []))
        _write_text(
            work_dir / "failed_images.txt",
            "\n".join(str(item) for item in batch_overview.get("失败图片", [])) + "\n",
        )
        _write_text(
            work_dir / "no_detection_images.txt",
            "\n".join(str(item) for item in batch_overview.get("无检测结果图片", [])) + "\n",
        )
        _write_text(
            work_dir / "poor_quality_images.txt",
            "\n".join(str(item) for item in batch_overview.get("质量较差图片", [])) + "\n",
        )
        _write_text(
            work_dir / "summary.txt",
            "\n".join(_summary_lines(batch_state, export_info)) + "\n",
        )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in work_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(work_dir).as_posix())
    finally:
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
        except OSError:
            pass  # 清理失败不掩盖导出成功
        try:
            if not zip_path.exists() and export_root.exists() and not any(export_root.iterdir()):
                export_root.rmdir()
        except OSError:
            pass
    _sync_report_path(batch_state, batch_state, zip_path, "zip_report_path")
    update_history_report_paths(batch_state, zip_path, storage_dir)
    return _file_component_output(zip_path), f"已导出：{zip_path}", batch_state


def export_batch_word_report(batch_state: list[dict[str, Any]], storage_dir: str):
    if not batch_state:
        raise gr.Error("请先完成批量检测，再导出合并 Word 报告。")
    batch_errors = batch_state[0].get("batch_errors", []) if batch_state else []
    if not isinstance(batch_errors, list):
        batch_errors = []
    overview = build_batch_summary(batch_state, batch_errors)
    overview["生成时间"] = datetime.now().isoformat(timespec="seconds")
    _ensure_storage_root(storage_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = report_dir(storage_dir) / f"batch_word_report_{stamp}"
    counter = 1
    while output_dir.exists():
        output_dir = report_dir(storage_dir) / f"batch_word_report_{stamp}_{counter:02d}"
        counter += 1
    try:
        path = export_batch_docx_report(batch_state, overview, output_dir)
    except Exception as exc:
        raise _friendly_gr_error(exc, "批量 Word 报告导出失败") from exc
    _sync_report_path(batch_state, batch_state, path, "word_report_path")
    update_history_report_paths(batch_state, path, storage_dir)
    return _file_component_output(path), f"已导出批量 Word 报告：{path}", batch_state


def export_single_report(batch_state: list[dict[str, Any]], selected_name: str, storage_dir: str):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    all_results = _item_results(item)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _ensure_storage_root(storage_dir)
    report_root, zip_path = _unique_report_paths(storage_dir, stamp)
    report_root.mkdir(parents=True, exist_ok=True)
    work_dir = report_root / "payload"
    images_dir = work_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    name = item.get("name") or item.get("image_name") or "当前单图"
    display_name = _item_display_name(item, str(name))
    stem = _safe_stem(name)
    advice = item.get("advice") or ""
    detections = _clean_detection_records(model_result_detections(result))
    model_items = []
    raw_summary = item.get("summary", {})
    summary_data = json_safe_value(raw_summary if isinstance(raw_summary, dict) else {})
    # 优先取 result 顶层 model，其次从摘要中的有效模型项回填。
    model_name = model_result_name(result, "")
    if not model_name:
        model_name = _summary_model_name(summary_data)
    if not model_name:
        model_name = "unknown"

    export_info = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "image_name": str(name),
        "display_name": display_name,
        "model": json_safe_value(model_name),
        "suggestion_type": text_value(item.get("suggestion_type", "default"), "default"),
        "safety_notice": SAFETY_NOTICE,
    }
    try:
        image_files = {
            "original": f"images/{stem}_original.png",
            "input": f"images/{stem}_input.png",
            "result": f"images/{stem}_result.png",
        }
        # None 检查：与批量导出保持一致，防止缺少图片时 AttributeError
        original_img = result.get("original")
        input_img = result.get("model_input")
        annotated_img = _report_annotated_image(result)
        if original_img is None or input_img is None or annotated_img is None:
            raise gr.Error(f"{name} 的结果不完整（缺少图片数据），无法导出报告。")
        save_png_image(original_img, work_dir / image_files["original"])
        save_png_image(input_img, work_dir / image_files["input"])
        save_png_image(annotated_img, work_dir / image_files["result"])
        for model_index, model_result in enumerate(all_results, start=1):
            model = model_result_name(model_result)
            model_detections = _clean_detection_records(model_result_detections(model_result))
            model_image_files = {}
            model_annotated = _report_annotated_image(model_result)
            if model_annotated is not None:
                model_result_file = f"images/{stem}_model_{model_index:02d}_{_safe_stem(model)}_result.png"
                save_png_image(model_annotated, work_dir / model_result_file)
                model_image_files["result"] = model_result_file
            model_items.append(
                {
                    "model": model,
                    "model_path": model_result_path(model_result),
                    "detections": model_detections,
                    "image_files": model_image_files,
                }
            )
        total_detections = sum(len(model_item["detections"]) for model_item in model_items)

        csv_path = work_dir / "detections.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["model", *TABLE_COLUMNS])
            writer.writeheader()
            for model_item in model_items:
                model = model_item["model"]
                model_detections = model_item["detections"]
                if model_detections:
                    for det in model_detections:
                        writer.writerow(csv_safe_row({"model": model, **{key: det.get(key, "") for key in TABLE_COLUMNS}}))
                else:
                    writer.writerow(csv_safe_row({"model": model, **{key: "" for key in TABLE_COLUMNS}}))

        _write_text(
            work_dir / "detections.json",
            json.dumps(
                json_safe_value(
                    {
                    "report": export_info,
                    "summary": summary_data,
                    "models": model_items,
                    "detections": detections,
                    "image_files": image_files,
                    }
                ),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
        )
        _write_text(work_dir / "suggestion.txt", advice)
        _write_text(
            work_dir / "summary.txt",
            "\n".join(
                [
                    "YOLO Dental Lesion Detection Single Report",
                    f"生成时间: {export_info['created_at']}",
                    f"图片名称: {name}",
                    f"列表显示名: {display_name}",
                    f"模型: {export_info['model']}",
                    f"建议类型: {export_info['suggestion_type']}",
                    f"主模型检测框数量: {len(detections)}",
                    f"全部模型检测框数量: {total_detections}",
                    f"安全声明: {SAFETY_NOTICE}",
                ]
            )
            + "\n",
        )
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>牙齿病变辅助检测报告</title>
  <style>
    body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 28px; color: #172033; }}
    h1 {{ font-size: 24px; }}
    .notice {{ padding: 12px 14px; background: #fff7ed; border-left: 4px solid #f97316; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    img {{ max-width: 100%; border: 1px solid #d7dde8; border-radius: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #d7dde8; padding: 8px; text-align: left; }}
    th {{ background: #eff4fb; }}
    pre {{ white-space: pre-wrap; background: #f6f8fb; padding: 12px; border-radius: 6px; }}
    .result-legend {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 12px 0 22px; }}
    .legend-item {{ border: 1px solid #d7dde8; border-radius: 6px; padding: 10px; }}
    .legend-swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 999px; margin-right: 6px; vertical-align: middle; }}
    .legend-item strong {{ margin-right: 6px; }}
    .legend-item span:last-child {{ display: block; color: #5d6b82; font-size: 13px; margin-top: 4px; line-height: 1.5; }}
  </style>
</head>
<body>
  <h1>牙齿病变辅助检测报告</h1>
  <p class="notice">{_html_escape(SAFETY_NOTICE)}</p>
  <p>生成时间：{_html_escape(export_info['created_at'])}</p>
  <p>图片名称：{_html_escape(name)}；列表显示名：{_html_escape(display_name)}；模型：{_html_escape(export_info['model'])}</p>
  <div class="grid">
    <figure><img src="{image_files['original']}"><figcaption>原始上传图</figcaption></figure>
    <figure><img src="{image_files['input']}"><figcaption>实际送入模型的图</figcaption></figure>
    <figure><img src="{image_files['result']}"><figcaption>检测结果图</figcaption></figure>
  </div>
  <h2>图例与类别说明</h2>
  {legend_html()}
  <h2>分模型结果图</h2>
  {_model_result_images_html(model_items)}
  <h2>检测框</h2>
  {_model_detections_html(all_results)}
  <h2>辅助建议</h2>
  <pre>{_html_escape(advice)}</pre>
  <h2>参数摘要</h2>
  <pre>{_html_escape(json.dumps(summary_data, ensure_ascii=False, indent=2, allow_nan=False))}</pre>
</body>
</html>
"""
        _write_text(work_dir / "report.html", html)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in work_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(work_dir).as_posix())
    finally:
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
        except OSError:
            pass  # 清理失败不掩盖导出成功
        try:
            if not zip_path.exists() and report_root.exists() and not any(report_root.iterdir()):
                report_root.rmdir()
        except OSError:
            pass
    _sync_report_path(batch_state, [item], zip_path, "zip_report_path")
    update_history_report_paths([item], zip_path, storage_dir)
    return _file_component_output(zip_path), f"已导出单图报告：{zip_path}", batch_state


def export_word_report(batch_state: list[dict[str, Any]], selected_name: str, storage_dir: str):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    name = item.get("name") or item.get("image_name") or "当前单图"
    display_name = _item_display_name(item, str(name))
    summary_data = item.get("summary", {})
    if not isinstance(summary_data, dict):
        summary_data = {}

    original_img = result.get("original")
    annotated_img = _report_annotated_image(result)
    if original_img is None or annotated_img is None:
        raise gr.Error(f"{name} 的结果不完整（缺少图片数据），无法导出 Word 报告。")

    model_name = model_result_name(result, "")
    if not model_name:
        model_name = _summary_model_name(summary_data)
    if not model_name:
        model_name = "unknown"

    _ensure_storage_root(storage_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = report_dir(storage_dir) / f"word_report_{stamp}_{_safe_stem(name)}"
    counter = 1
    while output_dir.exists():
        output_dir = report_dir(storage_dir) / f"word_report_{stamp}_{_safe_stem(name)}_{counter:02d}"
        counter += 1

    report_data = SingleReportData(
        image_name=f"{display_name}（原始文件：{name}）" if display_name != str(name) else str(name),
        created_at=datetime.now().isoformat(timespec="seconds"),
        model_name=str(model_name),
        original_image=original_img,
        model_input_image=result.get("model_input"),
        annotated_image=annotated_img,
        detections=_clean_detection_records(model_result_detections(result)),
        advice=item.get("advice") or "",
        quality_text=assess_image_quality(original_img),
        summary=summary_data,
        safety_notice=SAFETY_NOTICE,
        model_results=[
            {
                "model": model_result_name(model_result),
                "model_path": model_result_path(model_result),
                "detections": _clean_detection_records(model_result_detections(model_result)),
                "annotated": _report_annotated_image(model_result),
            }
            for model_result in _item_results(item)
        ],
    )
    try:
        path = export_single_docx_report(report_data, output_dir)
    except Exception as exc:
        raise _friendly_gr_error(exc, "Word 报告导出失败") from exc
    _sync_report_path(batch_state, [item], path, "word_report_path")
    update_history_report_paths([item], path, storage_dir)
    return _file_component_output(path), f"已导出 Word 报告：{path}", batch_state


def download_result_image(batch_state: list[dict[str, Any]], selected_name: str, storage_dir: str):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    image = result.get("annotated")
    if image is None:
        raise gr.Error("当前没有可下载的检测结果图。")
    name = item.get("name") or item.get("image_name") or "当前单图"
    _ensure_storage_root(storage_dir)
    try:
        path = save_result_image(image, storage_dir, name)
    except Exception as exc:
        raise _friendly_gr_error(exc, "检测结果图保存失败") from exc
    _remember_allowed_file_root(path.parent)
    return _file_component_output(path), f"已生成检测结果图：{path}"


def save_case_record(
    batch_state: list[dict[str, Any]],
    selected_name: str,
    case_id: str,
    case_note: str,
    storage_dir: str,
):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    _ensure_storage_root(storage_dir)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")
    case_id_text = str(case_id or "").strip()
    case_note_text = str(case_note or "").strip()
    image_name = item.get("name") or item.get("image_name") or "当前单图"
    safe_case = _safe_stem(case_id_text or image_name or "case")
    path = _unique_case_path(storage_dir, stamp, safe_case)
    payload = {
        "created_at": now.isoformat(timespec="seconds"),
        "case_id": case_id_text or "未填写",
        "note": case_note_text,
        "image_name": image_name,
        "display_name": _item_display_name(item, image_name),
        "summary": item.get("summary", {}),
        "model_results": _model_result_records(item),
        "detections": _clean_detection_records(model_result_detections(result)),
        "quality_text": item.get("quality_text") or assess_image_quality(result.get("original")),
        "quality_level": item.get("quality_level", ""),
        "report_path": item.get("report_path", ""),
        "word_report_path": item.get("word_report_path", ""),
        "zip_report_path": item.get("zip_report_path", ""),
        "suggestion_type": item.get("suggestion_type", "default"),
        "suggestion": item.get("advice", ""),
        "safety_notice": SAFETY_NOTICE,
    }
    _write_text(path, json.dumps(json_safe_value(payload), ensure_ascii=False, indent=2, allow_nan=False))
    rows = list_case_records(storage_dir)
    choices = _case_choices_from_rows(rows)
    # 精确匹配：choices 格式为 "created_at | case_id | image_name | filename.json"
    selected = next(
        (choice for choice in choices if choice.split("|")[-1].strip() == path.name),
        choices[0] if choices else None,
    )
    return (
        f"病例记录已保存：{path}",
        gr.update(choices=choices, value=selected),
        _case_table(rows),
        format_case_record(payload),
        _clear_file_output(),
        "",
    )


def refresh_case_records(storage_dir: str):
    _ensure_storage_root(storage_dir)
    rows = list_case_records(storage_dir)
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _case_table(rows),
        _case_detail_from_choice(selected, storage_dir),
        "已刷新病例记录。" if choices else "暂无病例记录。",
        _clear_file_output(),
        "",
    )


def search_case_records_ui(
    keyword: str,
    class_filter: str,
    level_filter: str,
    date_from: str,
    date_to: str,
    storage_dir: str,
):
    _ensure_storage_root(storage_dir)
    date_from, date_to = _validate_case_date_filters(date_from, date_to)
    rows = search_case_records(storage_dir, keyword, class_filter, level_filter, date_from, date_to)
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    message = f"已筛选到 {len(rows)} 条病例记录。" if rows else "未找到匹配病例记录。"
    return (
        gr.update(choices=choices, value=selected),
        _case_table(rows),
        _case_detail_from_choice(selected, storage_dir),
        message,
        _clear_file_output(),
        "",
    )


def delete_selected_case_record(
    choice: str,
    keyword: str,
    class_filter: str,
    level_filter: str,
    date_from: str,
    date_to: str,
    storage_dir: str,
):
    if not choice:
        raise gr.Error("请先选择要移入回收站的病例记录。")
    _ensure_storage_root(storage_dir)
    date_from, date_to = _validate_case_date_filters(date_from, date_to)
    file_name = _case_file_name_from_choice(choice)
    try:
        trash_path = move_case_to_trash(storage_dir, file_name)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise gr.Error(str(exc)) from exc
    rows = search_case_records(storage_dir, keyword, class_filter, level_filter, date_from, date_to)
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _case_table(rows),
        f"病例已移入回收站：{trash_path}",
        _case_detail_from_choice(selected, storage_dir),
        _clear_file_output(),
        "",
    )


def export_selected_case_record(choice: str, storage_dir: str):
    if not choice:
        raise gr.Error("请先选择要导出的病例记录。")
    _ensure_storage_root(storage_dir)
    file_name = _case_file_name_from_choice(choice)
    try:
        path = export_case_report(storage_dir, file_name)
    except (OSError, UnicodeDecodeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise gr.Error(f"病例文件损坏或无法读取：{exc}") from exc
    _remember_allowed_file_root(path.parent)
    return _file_component_output(path), f"已导出病例报告：{path}"


def load_case_record(choice: str, storage_dir: str):
    if not choice:
        return format_case_record({"提示": "暂无病例详情。选择已保存病例后，会在这里显示检测摘要、检测框和辅助建议。"})
    try:
        _ensure_storage_root(storage_dir)
    except gr.Error as exc:
        return format_case_record({"错误": str(exc)})
    try:
        file_name = _case_file_name_from_choice(choice)
    except gr.Error:
        return format_case_record({"错误": "病例选择无效，请刷新病例列表后重试。"})
    try:
        return format_case_record(load_case_record_data(storage_dir, file_name))
    except (OSError, UnicodeDecodeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        return format_case_record({"错误": f"病例文件损坏或无法读取：{exc}"})


def load_case_record_and_clear_export(choice: str, storage_dir: str):
    return load_case_record(choice, storage_dir), _clear_file_output(), ""


def refresh_history_records(storage_dir: str):
    _ensure_storage_root(storage_dir)
    rows = history_rows(storage_dir)
    choices = _history_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _history_table_from_rows(rows),
        load_history_record(selected, storage_dir) if selected else format_history_record(None),
        "历史记录已刷新。" if choices else "暂无检测历史。",
    )


def load_history_record(choice: str, storage_dir: str) -> str:
    try:
        _ensure_storage_root(storage_dir)
    except gr.Error as exc:
        return str(exc)
    return format_history_record(load_history_record_data(_history_id(choice), storage_dir))


def delete_selected_history_record(choice: str, storage_dir: str):
    _ensure_storage_root(storage_dir)
    record_id = _history_id(choice)
    if not record_id:
        history_select, table, detail, message = refresh_history_records(storage_dir)
        return history_select, table, detail, "请选择要删除的历史记录。"
    deleted = delete_history_record(record_id, storage_dir)
    history_select, table, detail, message = refresh_history_records(storage_dir)
    feedback = "已删除所选历史记录。" if deleted else "未找到所选历史记录，请刷新后重试。"
    return history_select, table, detail, feedback or message


def clear_all_history_records(storage_dir: str):
    _ensure_storage_root(storage_dir)
    clear_history_records(storage_dir)
    return (
        gr.update(choices=[], value=None),
        _history_table_from_rows([]),
        "请选择一条检测历史。",
        "历史记录已清空。病例记录不会被删除。",
    )


def clear_outputs():
    return (
        None,
        None,
        None,
        None,
        [],
        "暂无疑似区域局部图",
        _clear_file_output(),
        "",
        gr.update(value="下载检测结果图", interactive=False),
        gr.update(choices=[], value=[], interactive=False),
        _empty_table(),
        "",
        "等待上传图像",
        gr.update(value={}, visible=False),  # summary: 同时重置可见性
        gr.update(value="", visible=False),
        [],
        gr.update(choices=[], value=None),
        gr.update(),       # chatbot: 保留对话，不静默清空
        gr.update(),       # chat_state: 保留对话状态
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(value="导出 Word 报告", interactive=False),
        _clear_file_output(),
        "",
        gr.update(value="导出 ZIP 数据包", interactive=False),
        gr.update(value="完成检测后可保存", interactive=False),
    )


def clear_outputs_with_quality(image):
    values = list(clear_outputs())
    values[COMMON_OUTPUT_QUALITY_INDEX] = assess_image_quality(image)
    return tuple(values)


def run_single_detection(
    image,
    model_mode: str,
    primary_model_path: str,
    compare_model_path: str,
    conf: float,
    iou: float,
    device_choice: str,
    use_clahe: bool,
    enable_compare: bool,
    show_summary: bool,
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str,
    save_history: bool,
    history_limit: int | float,
):
    if image is None:
        raise gr.Error("请先上传一张牙科影像。")

    device, cuda_available = _device(device_choice)
    selected_models = _configured_models(model_mode if enable_compare else MODEL_MODE_SINGLE, primary_model_path, compare_model_path)
    _validate_model_files(selected_models)

    primary = None
    all_results = []
    for model_name, model_path in selected_models:
        result = _detect_model_path(model_name, model_path, image, use_clahe, conf, iou, device)
        all_results.append(result)
        if primary is None:
            primary = result

    if primary is None:
        raise gr.Error("推理失败：未能获取检测结果，请检查模型文件是否有效。")
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        env_api_key,
        direct_api_key_hidden,
        direct_api_key_visible,
        direct_key_visible,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
        advice_style,
    )
    advice = _build_advice(settings, _advice_detections(all_results))
    chat_history = _conversation_from_advice(advice)
    auto_save_warning = ""
    if settings.auto_save:
        auto_save_warning = _auto_save_conversation(chat_history, settings.storage_dir)
        if auto_save_warning:
            advice = f"{advice}\n\n{auto_save_warning}"
            chat_history = _conversation_from_advice(advice)
    quality_text, quality_level = _quality_payload(primary["original"])

    summary = {
        "运行设备": _device_label(device),
        "设备选择": device_choice,
        "CUDA可用": bool(cuda_available),
        "推理尺寸": 1280,
        "CLAHE增强": bool(use_clahe),
        "置信度阈值": conf,
        "IoU阈值": iou,
        "模型结果": [
            {
                "模型": item["model"],
                "检测数量": len(item["detections"]),
                "类别映射": item["class_names"],
                "路径": item.get("model_path", ""),
            }
            for item in all_results
        ],
    }

    batch_state = [
        {
            "name": "当前单图",
            "result": primary,
            "all_results": all_results,
            "advice": advice,
            "suggestion_type": _suggestion_type(settings.enabled),
            "quality_text": quality_text,
            "quality_level": quality_level,
            "summary": summary,
        }
    ]
    if save_history:
        history_warning = _auto_append_history(batch_state, settings.storage_dir, history_limit)
        if history_warning:
            advice = f"{advice}\n\n{history_warning}"
            chat_history = _conversation_from_advice(advice)
            batch_state[0]["advice"] = advice
    highres_image, crop_items, crop_text = _result_visual_outputs(primary)
    return (
        primary["original"],
        primary["model_input"],
        primary["annotated"],
        highres_image,
        crop_items,
        crop_text,
        _clear_file_output(),
        "",
        gr.update(value="下载检测结果图", interactive=True),
        _visible_class_update(primary),
        primary["table"],
        advice,
        quality_text,
        gr.update(value=summary, visible=show_summary),
        gr.update(value="", visible=False),
        batch_state,
        gr.update(choices=["当前单图"], value="当前单图"),
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(value="导出 Word 报告", interactive=True),
        _clear_file_output(),
        "",
        gr.update(value="导出 ZIP 数据包", interactive=True),
        gr.update(value="保存病例", interactive=True),
    )


def _file_name(file_obj) -> str:
    path = getattr(file_obj, "name", None) or str(file_obj)
    return Path(path).name


def run_batch_detection(
    files,
    model_mode: str,
    primary_model_path: str,
    compare_model_path: str,
    conf: float,
    iou: float,
    device_choice: str,
    use_clahe: bool,
    enable_compare: bool,
    show_summary: bool,
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str,
    save_history: bool,
    history_limit: int | float,
):
    if not files:
        raise gr.Error("请先批量上传牙科影像。")

    device, _ = _device(device_choice)
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        env_api_key,
        direct_api_key_hidden,
        direct_api_key_visible,
        direct_key_visible,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
        advice_style,
    )
    selected_models = _configured_models(model_mode if enable_compare else MODEL_MODE_SINGLE, primary_model_path, compare_model_path)
    _validate_model_files(selected_models)
    batch_state: list[dict[str, Any]] = []
    batch_errors: list[str] = []
    for index, file_obj in enumerate(files, start=1):
        path = getattr(file_obj, "name", None) or file_obj
        file_name = _file_name(file_obj)
        try:
            all_results = [
                _detect_model_path(model_name, model_path, path, use_clahe, conf, iou, device)
                for model_name, model_path in selected_models
            ]
            result = all_results[0]
            advice = _build_advice(settings, _advice_detections(all_results))
            quality_text, quality_level = _quality_payload(result["original"])
        except Exception as exc:
            batch_errors.append(f"{file_name}: {friendly_error_message(exc, '图片处理失败').splitlines()[0]}")
            continue
        batch_state.append(
            {
                "name": file_name,
                "display_name": f"{index:03d} - {file_name}",
                "result": result,
                "all_results": all_results,
                "advice": advice,
                "suggestion_type": _suggestion_type(settings.enabled),
                "quality_text": quality_text,
                "quality_level": quality_level,
                "summary": {
                    "文件": file_name,
                    "模型模式": model_mode if enable_compare else MODEL_MODE_SINGLE,
                    "模型结果": [
                        {
                            "模型": item["model"],
                            "模型路径": item.get("model_path", ""),
                            "检测数量": len(item["detections"]),
                            "类别映射": item["class_names"],
                        }
                        for item in all_results
                    ],
                    "CLAHE增强": bool(use_clahe),
                    "conf": conf,
                    "iou": iou,
                },
            }
        )

    if not batch_state:
        error_detail = "; ".join(batch_errors[:5])
        if len(batch_errors) > 5:
            error_detail += f" …等共 {len(batch_errors)} 张"
        raise gr.Error(f"所有图片处理失败：{error_detail}")

    first = batch_state[0]
    choices = [item["display_name"] for item in batch_state]
    first["batch_errors"] = batch_errors
    overview = build_batch_summary(batch_state, batch_errors)
    chat_history = _conversation_from_advice(first["advice"])
    auto_save_warning = ""
    if settings.auto_save:
        auto_save_warning = _auto_save_conversation(chat_history, settings.storage_dir)
        if auto_save_warning:
            first["advice"] = f"{first['advice']}\n\n{auto_save_warning}"
            chat_history = _conversation_from_advice(first["advice"])
    if save_history:
        history_warning = _auto_append_history(batch_state, settings.storage_dir, history_limit)
        if history_warning:
            first["advice"] = f"{first['advice']}\n\n{history_warning}"
            chat_history = _conversation_from_advice(first["advice"])
    highres_image, crop_items, crop_text = _result_visual_outputs(first["result"])
    return (
        first["result"]["original"],
        first["result"]["model_input"],
        first["result"]["annotated"],
        highres_image,
        crop_items,
        crop_text,
        _clear_file_output(),
        "",
        gr.update(value="下载检测结果图", interactive=True),
        _visible_class_update(first["result"]),
        first["result"]["table"],
        first["advice"],
        first.get("quality_text") or assess_image_quality(first["result"]["original"]),
        gr.update(value=first["summary"], visible=show_summary),
        gr.update(value=batch_overview_html(overview), visible=True),
        batch_state,
        gr.update(choices=choices, value=choices[0]),
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(value="导出 Word 报告", interactive=True),
        _clear_file_output(),
        "",
        gr.update(value="导出 ZIP 数据包", interactive=True),
        gr.update(value="保存病例", interactive=True),
    )


def select_batch_item(name: str, batch_state: list[dict[str, Any]], show_summary: bool):
    if not name or not batch_state:
        return (
            None,
            None,
            None,
            None,
            [],
            "暂无疑似区域局部图",
            _clear_file_output(),
            "",
            gr.update(value="下载检测结果图", interactive=False),
            gr.update(choices=[], value=[], interactive=False),
            _empty_table(),
            "",
            "等待上传图像",
            gr.update(value={}, visible=False),
            [],
            [],
            _clear_file_output(),
            "",
            _clear_file_output(),
            "",
            gr.update(value="导出 Word 报告", interactive=False),
            _clear_file_output(),
            "",
            gr.update(value="导出 ZIP 数据包", interactive=False),
            gr.update(value="完成检测后可保存", interactive=False),
        )
    item = next((row for row in batch_state if _matches_item_name(row, name)), None)
    if item is None:
        raise gr.Error("当前选择的结果已失效，请重新选择图片。")
    chat_history = _conversation_from_advice(item["advice"])
    result = item["result"]
    result.pop("_visible_detections", None)
    if result.get("full_annotated") is not None:
        result["annotated"] = result["full_annotated"]
    highres_image, crop_items, crop_text = _result_visual_outputs(result)
    word_path = _path_text(item.get("word_report_path"))
    zip_path = _path_text(item.get("zip_report_path"))
    return (
        result["original"],
        result["model_input"],
        result["annotated"],
        highres_image,
        crop_items,
        crop_text,
        _clear_file_output(),
        "",
        gr.update(value="下载检测结果图", interactive=True),
        _visible_class_update(result),
        result["table"],
        item["advice"],
        item.get("quality_text") or assess_image_quality(result["original"]),
        gr.update(value=item["summary"], visible=show_summary),
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        _file_component_output(word_path),
        word_path,
        gr.update(value="导出 Word 报告", interactive=True),
        _file_component_output(zip_path),
        zip_path,
        gr.update(value="导出 ZIP 数据包", interactive=True),
        gr.update(value="保存病例", interactive=True),
    )


def update_detection_visibility(visible_classes: list[str], selected_name: str, batch_state: list[dict[str, Any]]):
    if not batch_state:
        return None, None, [], "暂无疑似区域局部图", [], _empty_table(), _clear_file_output(), ""
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    base_image = _first_present(result.get("model_input"), result.get("original"))
    if base_image is None:
        raise gr.Error("当前结果缺少可重绘的图像，请重新检测。")
    detections = _clean_detection_records(model_result_detections(result))
    visible_set = None if visible_classes is None else {str(item).strip() for item in visible_classes if str(item).strip()}
    if visible_set is None:
        result["_visible_detections"] = detections
    else:
        result["_visible_detections"] = [
            row
            for row in detections
            if (str(row.get("中文名称") or "").strip() in visible_set or str(row.get("class") or "").strip() in visible_set)
        ]
    result["annotated"] = draw_detections_with_filter(base_image, detections, visible_classes)
    highres_image, crop_items, crop_text = _result_visual_outputs(result)
    # 类别开关只改变可视化结果和局部图，检测表仍保留完整检测结果，
    # 避免用户误以为被隐藏的检测框已经从结果中删除。
    table = _table_from_records(detections) if detections else _empty_table()
    return (
        result["annotated"],
        highres_image,
        crop_items,
        crop_text,
        batch_state,
        table,
        _clear_file_output(),
        "",
    )


def test_ai_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str,
):
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        env_api_key,
        direct_api_key_hidden,
        direct_api_key_visible,
        direct_key_visible,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
        advice_style,
    )
    if not settings.enabled:
        return "AI 功能未开启。开启后可测试接口。"
    try:
        return test_chat_completion(settings)
    except Exception as exc:
        return friendly_error_message(exc, "AI 接口测试失败")


def save_ui_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str,
    enable_compare: bool,
    show_summary: bool,
    model_mode: str,
    model_dir: str,
    primary_model_path: str,
    compare_model_path: str,
    save_history: bool,
    history_limit: int | float,
):
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        env_api_key,
        direct_api_key_hidden,
        direct_api_key_visible,
        direct_key_visible,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
        advice_style,
    )
    settings.enable_compare = bool(enable_compare)
    settings.advice_style = advice_style if advice_style in {"简洁版", "医生版", "患者版"} else "简洁版"
    settings.show_summary = bool(show_summary)
    settings.model_mode = (model_mode or MODEL_MODE_SINGLE) if settings.enable_compare else MODEL_MODE_SINGLE
    settings.model_dir = _model_dir_or_default(model_dir)
    settings.primary_model_path = _model_path_or_default(primary_model_path, str(DEFAULT_MODEL_PATH))
    settings.compare_model_path = _model_path_or_default(
        compare_model_path,
        str(MODEL_REGISTRY[MODEL_SOURCE]["path"]),
    )
    if settings.enable_compare:
        _validate_compare_model_selection(settings.model_mode, settings.primary_model_path, settings.compare_model_path)
    settings.save_history = bool(save_history)
    settings.history_limit = _normalize_history_limit(history_limit)
    try:
        path = save_settings(settings)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        text = str(exc).casefold()
        context = (
            "存储目录不可用"
            if ("file exists" in text or "not a directory" in text or "不是目录" in text)
            else "设置保存失败"
        )
        raise _friendly_gr_error(exc, context) from exc
    _ensure_storage_root(settings.storage_dir)
    feedback = [f"设置已保存：{path}"]
    case_rows = list_case_records(settings.storage_dir)
    case_choices = _case_choices_from_rows(case_rows)
    case_selected = case_choices[0] if case_choices else None
    case_message = "病例列表已同步到当前存储位置。" if case_choices else "当前存储位置暂无病例记录。"
    history_table = history_rows(settings.storage_dir)
    history_choices = _history_choices_from_rows(history_table)
    history_selected = history_choices[0] if history_choices else None
    history_message = "检测历史已同步到当前存储位置。" if history_choices else "当前存储位置暂无检测历史。"
    return (
        _toast("\n".join(feedback), "success"),
        gr.update(choices=case_choices, value=case_selected),
        _case_table(case_rows),
        _case_detail_from_choice(case_selected, settings.storage_dir),
        case_message,
        gr.update(choices=history_choices, value=history_selected),
        _history_table_from_rows(history_table),
        load_history_record(history_selected, settings.storage_dir) if history_selected else format_history_record(None),
        history_message,
        _clear_file_output(),
        "",
    )


def continue_chat(
    message: str,
    history: list[dict[str, str]],
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    env_api_key: str,
    direct_api_key_hidden: str,
    direct_api_key_visible: str,
    direct_key_visible: bool,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
    advice_style: str,
):
    user_message = (message or "").strip()
    if not user_message:
        return history, history, "", _clear_file_output(), ""
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        env_api_key,
        direct_api_key_hidden,
        direct_api_key_visible,
        direct_key_visible,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
        advice_style,
    )
    history = _normalize_chat_history(history)
    user_entry = {"role": "user", "content": user_message}
    clear_input = True
    if not settings.enabled:
        history.append(user_entry)
        history.append(
            {
                "role": "assistant",
                "content": "AI 功能未开启。当前只能查看检测后的内置建议。",
            }
        )
    else:
        try:
            style_prompt = _advice_style_prompt(settings.advice_style)
            system_prompt = settings.custom_prompt
            if style_prompt:
                system_prompt = f"{system_prompt}\n{style_prompt}"
            messages = [{"role": "system", "content": system_prompt}, *history, user_entry]
            answer = chat_completion(settings, messages, temperature=0.2, max_tokens=500)
        except Exception as exc:
            answer = friendly_error_message(exc, "AI 回复失败")
            clear_input = False
        history.append(user_entry)
        if answer.strip():
            history.append({"role": "assistant", "content": answer})
        else:
            history.append({"role": "assistant", "content": "AI 未返回有效内容，请重试或检查接口配置。"})
            clear_input = False
    if settings.auto_save:
        auto_save_warning = _auto_save_conversation(history, settings.storage_dir)
        if auto_save_warning:
            history.append({"role": "assistant", "content": auto_save_warning})
            clear_input = False
    return history, history, "" if clear_input else user_message, _clear_file_output(), ""


def export_chat(history: list[dict[str, str]], storage_dir: str):
    history = _normalize_chat_history(history)
    if not history:
        raise gr.Error("当前没有可导出的对话记录。")
    _ensure_storage_root(storage_dir)
    path = save_conversation(history, storage_dir)
    _remember_allowed_file_root(path.parent)
    return _file_component_output(path), f"已导出：{path}"


def toggle_ai_settings(enabled: bool):
    return gr.update(visible=enabled)


def set_api_key_mode(key_mode: str):
    direct_mode = key_mode == "直接 Key 值"
    return (
        gr.update(visible=not direct_mode),
        gr.update(visible=direct_mode),
        gr.update(visible=False),
        gr.update(visible=direct_mode, value="显示 Key"),
        False,
    )


def toggle_direct_key_visibility(hidden_key: str, visible_key: str, direct_key_visible: bool):
    next_visible = not bool(direct_key_visible)
    key_value = visible_key if direct_key_visible else hidden_key
    return (
        gr.update(value=key_value, visible=not next_visible),
        gr.update(value=key_value, visible=next_visible),
        gr.update(value="隐藏 Key" if next_visible else "显示 Key"),
        next_visible,
    )


def toggle_summary(show_summary: bool):
    return gr.update(visible=show_summary)


def toggle_model_mode(model_mode: str):
    return gr.update(visible=model_mode == MODEL_MODE_COMPARE)


def on_enable_compare_change(enable_compare: bool):
    """关闭'允许对比模型模式'时，强制模型模式回到单模型。"""
    if not enable_compare:
        return (
            gr.update(value=MODEL_MODE_SINGLE),
            gr.update(value=MODEL_MODE_SINGLE),
            gr.update(visible=False),
        )
    return gr.update(), gr.update(), gr.update()


def sync_model_mode(model_mode: str):
    return gr.update(value=model_mode), gr.update(visible=model_mode == MODEL_MODE_COMPARE)


def default_storage_dir():
    return str(APP_HOME), _toast(f"已恢复默认数据目录：{APP_HOME}。保存设置后生效。")


def choose_storage_dir(storage_dir: str):
    selected = _choose_directory_dialog("选择数据存储目录", storage_dir or APP_HOME)
    if not selected:
        return gr.update(), _toast("未选择新的数据存储目录。")
    root = _safe_existing_root(selected)
    if root is None:
        return gr.update(), _toast("选择的数据存储目录不可访问，请手动检查路径后重试。", "error")
    path = str(root)
    return gr.update(value=path), _toast(f"已选择数据存储目录：{path}。保存设置后生效。")


def _with_current_defaults(saved: AiSettings, *, config_exists: bool = False) -> AiSettings:
    # 仅当 settings.json 不存在（首次运行）时才迁移旧默认配置。
    # 若文件已存在，说明用户已保存过设置，不应静默覆盖。
    if not config_exists:
        if (
            saved.base_url == "https://api.openai.com/v1"
            and saved.model == "gpt-4o-mini"
            and saved.key_mode == "环境变量"
            and saved.api_key in {"", "OPENAI_API_KEY"}
        ):
            saved.base_url = DEFAULT_AI_BASE_URL
            saved.model = DEFAULT_AI_MODEL
            saved.api_key = DEFAULT_AI_KEY_ENV
        if (saved.custom_prompt or "").strip().lower() in {"", "prompt"}:
            saved.custom_prompt = DEFAULT_AI_PROMPT
    return saved


def build_app() -> gr.Blocks:
    saved = _with_current_defaults(load_settings(), config_exists=CONFIG_PATH.exists())
    try:
        _ensure_storage_root(saved.storage_dir)
    except gr.Error:
        saved.storage_dir = str(APP_HOME)
        _ensure_storage_root(saved.storage_dir)
    env_key_value, direct_key_value = _api_key_inputs(saved)
    model_choices = scan_model_files(saved.model_dir)
    model_choice_values = {value for _, value in model_choices}
    initial_case_rows = list_case_records(saved.storage_dir)
    initial_history_rows = history_rows(saved.storage_dir)
    saved_primary_model_path = _model_path_or_default(saved.primary_model_path, str(DEFAULT_MODEL_PATH))
    model_card_choices = _model_card_choices()
    selected_model_choice = (
        saved_primary_model_path
        if saved_primary_model_path in model_choice_values
        else (model_choices[0][1] if model_choices else None)
    )
    device_choices = _device_choices()
    with gr.Blocks(
        title="牙齿病变区域识别",
        elem_classes=["app-shell"],
    ) as demo:
        batch_state = gr.State([])
        chat_state = gr.State([])
        gr.HTML(
            """
            <header class="app-header">
              <div>
                <div class="eyebrow">医院与个人辅助筛查工作台</div>
                <h1 class="app-title">牙齿病变区域识别</h1>
                <p class="app-subtitle">上传牙科影像，查看模型输入、检测框和辅助建议。结果仅供参考，不能替代专业牙科医生诊断。</p>
              </div>
              <span class="status-badge">Dental AI Workbench</span>
            </header>
            """
        )

        with gr.Tabs(elem_classes=["main-tabs"]):
            with gr.Tab("检测工作台"):
                with gr.Group(elem_classes=["section-card", "guide-card"]):
                    gr.HTML(
                        '<div class="guide-steps">'
                        '<span>1. 上传影像</span>'
                        '<span>2. 开始分析</span>'
                        '<span>3. 查看结果</span>'
                        '<span>4. 保存或导出</span>'
                        '</div>'
                    )
                    with gr.Accordion("使用说明", open=False):
                        gr.Markdown(
                            "支持 PNG、JPG、JPEG、BMP、WEBP、TIF、TIFF 格式图片。\n\n"
                            "置信度表示模型对检测框的把握程度，不等同于疾病严重程度。\n\n"
                            "CLAHE 适合低对比度牙片；如果图像本身清晰，可保持关闭。\n\n"
                            "报告默认导出完整检测结果；界面中的类别显示开关只影响当前查看和结果图下载。\n\n"
                            f"{SAFETY_NOTICE}"
                        )
                with gr.Row(elem_classes=["workbench-grid"]):
                    with gr.Column(scale=4, elem_classes=["control-panel"]):
                        with gr.Group(elem_classes=["section-card", "upload-card"]):
                            with gr.Tabs(elem_classes=["sub-tabs"]):
                                with gr.Tab("单张分析"):
                                    gr.HTML(
                                        '<div class="section-heading"><h2>上传影像</h2>'
                                        '<p>拖拽牙科影像到此处，支持常见图片格式。</p></div>'
                                    )
                                    image = gr.Image(
                                        type="pil",
                                        label="上传牙科影像",
                                        show_label=False,
                                        height=280,
                                        sources=["upload", "clipboard"],
                                        placeholder="拖拽牙科影像到此处\n支持常见图片格式",
                                        elem_classes=["upload-input"],
                                    )
                                    run_btn = gr.Button(
                                        "开始分析",
                                        variant="primary",
                                        elem_classes=["primary-action"],
                                    )
                                    with gr.Accordion("示例图片", open=False):
                                        example_select = gr.Dropdown(
                                            label="选择脱敏示例",
                                            choices=_example_choices(),
                                            value=None,
                                        )
                                        load_example_btn = gr.Button(
                                            "加载示例",
                                            elem_classes=["secondary-action", "compact-button"],
                                        )
                                        example_info = gr.Textbox(
                                            label="示例说明",
                                            value="选择示例后会在这里显示说明。",
                                            interactive=False,
                                            lines=4,
                                        )
                                with gr.Tab("批量分析"):
                                    gr.HTML(
                                        '<div class="section-heading"><h2>批量上传</h2>'
                                        '<p>批量分析会按当前模型模式逐张检测，可在完成后导出结果包。</p></div>'
                                    )
                                    batch_files = gr.File(
                                        label="批量上传图片",
                                        show_label=False,
                                        file_count="multiple",
                                        file_types=[".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"],
                                        elem_classes=["upload-input"],
                                    )
                                    batch_btn = gr.Button(
                                        "批量分析",
                                        variant="primary",
                                        elem_classes=["primary-action"],
                                    )
                                    batch_select = gr.Dropdown(label="查看图片", choices=[])
                                    with gr.Row(elem_classes=["compact-row"]):
                                        export_batch_btn = gr.Button(
                                            "导出批量结果",
                                            interactive=False,
                                            elem_classes=["secondary-action"],
                                        )
                                        export_batch_word_btn = gr.Button(
                                            "导出批量 Word",
                                            interactive=False,
                                            elem_classes=["secondary-action"],
                                        )
                                        batch_export_file = gr.File(label="批量结果 ZIP", visible=False)
                                        batch_word_file = gr.File(label="批量 Word 报告", visible=False)
                                    batch_export_path = gr.Textbox(
                                        label="批量导出路径",
                                        interactive=False,
                                        lines=1,
                                        max_lines=1,
                                        elem_classes=["path-output"],
                                    )
                                    batch_word_path = gr.Textbox(
                                        label="批量 Word 报告路径",
                                        interactive=False,
                                        lines=1,
                                        max_lines=1,
                                        elem_classes=["path-output"],
                                    )
                                    batch_overview = gr.HTML(visible=False)

                        with gr.Group(elem_classes=["section-card", "panel-card"]):
                            gr.HTML('<div class="section-heading"><h2>推理设置</h2></div>')
                            model_mode = gr.Radio(
                                choices=[MODEL_MODE_SINGLE, MODEL_MODE_COMPARE],
                                value=saved.model_mode if saved.enable_compare else MODEL_MODE_SINGLE,
                                label="模型模式",
                                elem_classes=["segmented-control"],
                            )
                            if len(device_choices) > 2:
                                device_choice = gr.Dropdown(
                                    choices=device_choices,
                                    value=_default_device_choice(),
                                    label="推理设备",
                                    elem_classes=["compact-control"],
                                )
                            else:
                                device_choice = gr.Radio(
                                    choices=device_choices,
                                    value=_default_device_choice(),
                                    label="推理设备",
                                    elem_classes=["segmented-control"],
                                )
                            with gr.Row(elem_classes=["compact-row"]):
                                conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度")
                                iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU")
                            use_clahe = gr.Checkbox(
                                value=False,
                                label="CLAHE 增强",
                                info="适合低对比度牙片，默认关闭。",
                            )

                    with gr.Column(scale=7, elem_classes=["result-panel"]):
                        with gr.Row(elem_classes=["image-grid"]):
                            with gr.Column(elem_classes=["image-panel"]):
                                gr.HTML('<div class="image-title">原图</div>')
                                original_output = gr.Image(
                                    type="pil",
                                    label="原图",
                                    show_label=False,
                                    height=240,
                                    placeholder="等待上传",
                                    elem_classes=["result-card"],
                                )
                            with gr.Column(elem_classes=["image-panel"]):
                                gr.HTML('<div class="image-title">模型输入</div>')
                                model_input_output = gr.Image(
                                    type="pil",
                                    label="模型输入",
                                    show_label=False,
                                    height=240,
                                    placeholder="完成检测后显示",
                                    elem_classes=["result-card"],
                                )
                            with gr.Column(elem_classes=["image-panel"]):
                                gr.HTML('<div class="image-title">检测结果</div>')
                                result_output = gr.Image(
                                    type="pil",
                                    label="检测结果",
                                    show_label=False,
                                    height=240,
                                    placeholder="完成检测后显示",
                                    elem_classes=["result-card"],
                                )
                        with gr.Accordion("查看高清结果与疑似区域", open=False):
                            highres_result_output = gr.Image(
                                type="pil",
                                label="高清结果图",
                                height=420,
                                interactive=False,
                                elem_classes=["result-card", "highres-result-card"],
                            )
                            crop_status = gr.Markdown("暂无疑似区域局部图")
                            crop_gallery = gr.Gallery(
                                label="疑似区域局部图",
                                columns=3,
                                rows=1,
                                height=220,
                                allow_preview=True,
                                object_fit="contain",
                            )
                            with gr.Row(elem_classes=["path-row"]):
                                result_image_path = gr.Textbox(
                                    label="检测结果图路径",
                                    interactive=False,
                                    lines=1,
                                    max_lines=1,
                                    scale=8,
                                    elem_classes=["path-output"],
                                )
                                download_result_btn = gr.Button(
                                    "下载检测结果图",
                                    interactive=False,
                                    elem_classes=["secondary-action"],
                                    scale=2,
                                )
                                result_image_file = gr.File(label="检测结果图 PNG", visible=False)
                        with gr.Group(elem_classes=["section-card", "result-table-card"]):
                            gr.HTML(legend_html())
                            visible_class_filter = gr.CheckboxGroup(
                                label="显示类别",
                                choices=[],
                                value=[],
                                interactive=False,
                                elem_classes=["compact-control"],
                            )
                            det_table = gr.Dataframe(
                                value=_empty_table(),
                                headers=TABLE_COLUMNS,
                                label="检测框",
                                wrap=False,
                                interactive=False,
                            )
                        with gr.Row(elem_classes=["insight-grid"]):
                            advice_box = gr.Textbox(
                                label="牙齿辅助建议",
                                lines=7,
                                interactive=False,
                                elem_classes=["panel-card"],
                            )
                            quality_box = gr.Textbox(
                                value="等待上传图像",
                                label="图像质量提示",
                                lines=7,
                                interactive=False,
                                elem_classes=["panel-card"],
                            )
                        summary = gr.JSON(label="参数摘要", visible=False)
                        with gr.Group(elem_classes=["section-card", "export-toolbar"]):
                            with gr.Row(elem_classes=["path-row"]):
                                word_report_path = gr.Textbox(
                                    label="Word 报告路径",
                                    interactive=False,
                                    lines=1,
                                    max_lines=1,
                                    scale=8,
                                    elem_classes=["path-output"],
                                )
                                export_word_btn = gr.Button(
                                    "导出 Word 报告",
                                    interactive=False,
                                    elem_classes=["secondary-action"],
                                    scale=2,
                                )
                                word_report_file = gr.File(label="Word 报告", visible=False)
                            with gr.Row(elem_classes=["path-row"]):
                                report_path = gr.Textbox(
                                    label="ZIP 数据包路径",
                                    interactive=False,
                                    lines=1,
                                    max_lines=1,
                                    scale=8,
                                    elem_classes=["path-output"],
                                )
                                export_report_btn = gr.Button(
                                    "导出 ZIP 数据包",
                                    interactive=False,
                                    elem_classes=["secondary-action"],
                                    scale=2,
                                )
                                report_file = gr.File(label="单图报告 ZIP", visible=False)

            with gr.Tab("AI 问答"):
                with gr.Group(elem_classes=["section-card", "chat-card"]):
                    gr.HTML(
                        '<div class="card-heading"><div><h2>AI 问答</h2>'
                        '<p>完成检测后，可以继续追问关注区域和复查建议。</p></div>'
                        '<span class="status-badge">自动保存可在设置中调整</span></div>'
                    )
                    chatbot = gr.Chatbot(
                        label="问答记录",
                        show_label=False,
                        height=500,
                        placeholder="暂无对话。完成检测后，可以继续追问病变位置、可能风险和复查建议。",
                        elem_classes=["chat-window"],
                    )
                    with gr.Row(elem_classes=["chat-input-row"]):
                        chat_input = gr.Textbox(
                            label="继续提问",
                            placeholder="例如：这个结果需要重点复查哪些位置？",
                            scale=7,
                        )
                        chat_btn = gr.Button(
                            "发送",
                            variant="primary",
                            scale=1,
                            elem_classes=["primary-action", "compact-button"],
                        )
                    with gr.Row(elem_classes=["path-row"]):
                        export_path = gr.Textbox(
                            label="导出路径",
                            interactive=False,
                            lines=1,
                            max_lines=1,
                            scale=8,
                            elem_classes=["path-output"],
                        )
                        export_btn = gr.Button(
                            "导出对话",
                            scale=2,
                            elem_classes=["secondary-action"],
                        )
                        export_file = gr.File(label="导出的对话文件", visible=False)

            with gr.Tab("病例记录"):
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML(
                        '<div class="card-heading"><div><h2>病例记录</h2>'
                        '<p>保存检测摘要、检测框和建议，便于后续复查。</p></div></div>'
                    )
                    with gr.Row(elem_classes=["compact-row"]):
                        case_id = gr.Textbox(
                            label="病例编号 / 备注名称",
                            placeholder="例如：20260602-复查",
                            lines=1,
                            max_lines=1,
                        )
                        case_note = gr.Textbox(label="病例备注", placeholder="可填写主诉、复查说明或医生备注", lines=3)
                    with gr.Row(elem_classes=["compact-row"]):
                        save_case_btn = gr.Button(
                            "完成检测后可保存",
                            variant="primary",
                            interactive=False,
                            elem_classes=["primary-action", "compact-button"],
                        )
                        refresh_case_btn = gr.Button(
                            "刷新记录",
                            elem_classes=["secondary-action", "compact-button"],
                        )
                    case_feedback = gr.Textbox(label="病例反馈", interactive=False, lines=3)
                    with gr.Accordion("说明", open=False):
                        gr.Markdown("病例记录仅保存检测摘要、检测框和建议，不自动保存原始牙片图片。")
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML('<div class="section-heading"><h2>已保存病例</h2><p>选择记录后查看结构化详情。</p></div>')
                    with gr.Row(elem_classes=["compact-row"]):
                        case_keyword = gr.Textbox(
                            label="搜索病例",
                            placeholder="病例编号、图片名称、备注、类别或建议",
                            lines=1,
                            max_lines=1,
                        )
                        case_class_filter = gr.Dropdown(
                            label="类别筛选",
                            choices=["全部", "龋齿", "根尖周病变", "阻生牙", "无检测结果"],
                            value="全部",
                        )
                        case_level_filter = gr.Dropdown(
                            label="关注等级筛选",
                            choices=["全部", "重点关注", "建议复查", "低置信度参考", "无检测结果"],
                            value="全部",
                        )
                    with gr.Row(elem_classes=["compact-row"]):
                        case_date_from = gr.Textbox(label="开始日期", placeholder="YYYY-MM-DD", lines=1, max_lines=1)
                        case_date_to = gr.Textbox(label="结束日期", placeholder="YYYY-MM-DD", lines=1, max_lines=1)
                    with gr.Row(elem_classes=["compact-row"]):
                        search_case_btn = gr.Button("搜索/筛选", elem_classes=["secondary-action", "compact-button"])
                        delete_case_btn = gr.Button("移入回收站", elem_classes=["secondary-action", "compact-button"])
                        export_case_btn = gr.Button("导出病例报告", elem_classes=["secondary-action", "compact-button"])
                    case_select = gr.Dropdown(label="已保存病例", choices=_case_choices_from_rows(initial_case_rows))
                    case_table = gr.Dataframe(
                        value=_case_table(initial_case_rows),
                        headers=CASE_TABLE_COLUMNS,
                        label="病例列表",
                        wrap=False,
                        interactive=False,
                    )
                    case_report_file = gr.File(label="病例报告 Word", visible=False)
                    case_report_path = gr.Textbox(
                        label="病例报告路径",
                        interactive=False,
                        lines=1,
                        max_lines=1,
                        elem_classes=["path-output"],
                    )
                    case_detail = gr.Textbox(
                        value=format_case_record(None),
                        label="病例详情",
                        interactive=False,
                        lines=14,
                    )

            with gr.Tab("检测历史"):
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML(
                        '<div class="card-heading"><div><h2>检测历史</h2>'
                        '<p>自动保存最近检测摘要，默认不保存原始上传图。</p></div></div>'
                    )
                    with gr.Row(elem_classes=["compact-row"]):
                        refresh_history_btn = gr.Button("刷新历史", elem_classes=["secondary-action", "compact-button"])
                        delete_history_btn = gr.Button("删除所选", elem_classes=["secondary-action", "compact-button"])
                        clear_history_btn = gr.Button("清空历史", elem_classes=["secondary-action", "compact-button"])
                    history_feedback = gr.Textbox(label="历史反馈", interactive=False, lines=2)
                    history_select = gr.Dropdown(
                        label="检测历史",
                        choices=_history_choices_from_rows(initial_history_rows),
                    )
                    history_table = gr.Dataframe(
                        value=_history_table_from_rows(initial_history_rows),
                        headers=HISTORY_TABLE_COLUMNS,
                        label="历史列表",
                        wrap=False,
                        interactive=False,
                    )
                    history_detail = gr.Textbox(
                        value=format_history_record(None),
                        label="历史详情",
                        interactive=False,
                        lines=14,
                    )

            with gr.Tab("设置"):
                with gr.Tabs(elem_classes=["settings-tabs"]):
                    with gr.Tab("检测显示"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>显示选项</h2><p>控制主工作台中展示的分析能力。</p></div>')
                            enable_compare = gr.Checkbox(value=saved.enable_compare, label="允许对比模型模式")
                            show_summary = gr.Checkbox(value=saved.show_summary, label="显示参数分析摘要")
                            with gr.Accordion("帮助", open=False):
                                gr.Markdown("对比模型会在单张分析时运行两组模型；参数摘要用于查看推理配置和检测数量。")
                    with gr.Tab("模型选择"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>模型选择</h2><p>普通用户可直接选择推荐卡片，高级路径配置保留在下方。</p></div>')
                            model_cards_view = gr.HTML(model_cards_html(_model_cards(saved_primary_model_path), saved_primary_model_path))
                            model_card_select = gr.Radio(
                                choices=model_card_choices,
                                value=saved_primary_model_path if any(saved_primary_model_path == value for _, value in model_card_choices) else None,
                                label="模型卡片",
                                elem_classes=["segmented-control"],
                            )
                            apply_model_card_btn = gr.Button(
                                "使用模型卡片",
                                elem_classes=["secondary-action", "compact-button"],
                            )
                            settings_model_mode = gr.Radio(
                                choices=[MODEL_MODE_SINGLE, MODEL_MODE_COMPARE],
                                value=saved.model_mode if saved.enable_compare else MODEL_MODE_SINGLE,
                                label="模型模式",
                                elem_classes=["segmented-control"],
                            )
                            with gr.Accordion("高级模型路径设置", open=False):
                                with gr.Row(elem_classes=["path-row"]):
                                    model_dir = gr.Textbox(
                                        value=_model_dir_or_default(saved.model_dir),
                                        label="模型目录",
                                        lines=1,
                                        max_lines=1,
                                        scale=8,
                                    )
                                    open_model_dir_btn = gr.Button(
                                        "...",
                                        size="sm",
                                        scale=1,
                                        elem_classes=["icon-action"],
                                    )
                                    refresh_model_btn = gr.Button(
                                        "刷新",
                                        scale=2,
                                        elem_classes=["secondary-action"],
                                    )
                                with gr.Row(elem_classes=["model-row"]):
                                    model_file_select = gr.Dropdown(
                                        choices=model_choices,
                                        value=selected_model_choice,
                                        label="目录内模型",
                                        scale=8,
                                    )
                                    apply_model_btn = gr.Button(
                                        "使用选中模型",
                                        elem_classes=["secondary-action"],
                                        scale=2,
                                    )
                                with gr.Row(elem_classes=["compact-row"]):
                                    model_apply_target = gr.Radio(
                                        choices=["主模型", "对比模型"],
                                        value="主模型",
                                        label="填入位置",
                                        elem_classes=["segmented-control"],
                                    )
                                primary_model_path = gr.Textbox(
                                    value=_model_path_or_default(saved.primary_model_path, str(DEFAULT_MODEL_PATH)),
                                    label="主模型路径",
                                    lines=1,
                                    max_lines=1,
                                )
                                compare_model_path = gr.Textbox(
                                    value=_model_path_or_default(
                                        saved.compare_model_path,
                                        str(MODEL_REGISTRY[MODEL_SOURCE]["path"]),
                                    ),
                                    label="对比模型路径",
                                    lines=1,
                                    max_lines=1,
                                    visible=saved.enable_compare and saved.model_mode == MODEL_MODE_COMPARE,
                                )
                            with gr.Row(elem_classes=["compact-row"]):
                                test_model_btn = gr.Button(
                                    "测试模型",
                                    elem_classes=["secondary-action", "compact-button"],
                                )
                            model_feedback = gr.Textbox(label="模型反馈", interactive=False, lines=2)
                            with gr.Accordion("帮助", open=False):
                                gr.Markdown("刷新会扫描模型目录及子目录中的受支持模型文件；三点按钮用于弹出路径选择器并切换模型目录。")
                    with gr.Tab("模型说明"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>模型说明</h2><p>识别类别、输入要求、适用边界与安全声明。</p></div>')
                            model_info_markdown = gr.Markdown(_current_model_info_markdown(saved_primary_model_path))
                            gr.HTML(legend_html())
                    with gr.Tab("AI 建议"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>AI 建议</h2><p>配置检测后的辅助建议与追问能力。</p></div>')
                            ai_enabled = gr.Checkbox(value=saved.enabled, label="启用 AI 建议与问答")
                            advice_style = gr.Dropdown(
                                choices=["简洁版", "医生版", "患者版"],
                                value=saved.advice_style,
                                label="AI 建议风格",
                            )
                            with gr.Group(visible=saved.enabled, elem_classes=["panel-card"]) as ai_group:
                                with gr.Row(elem_classes=["compact-row"]):
                                    ai_model = gr.Textbox(value=saved.model, label="模型")
                                    base_url = gr.Textbox(
                                        value=saved.base_url,
                                        label="Base URL",
                                        info="仅支持 OpenAI 兼容 Chat Completions 接口。无路径时自动追加 /v1。",
                                    )
                                key_mode = gr.Radio(
                                    choices=["环境变量", "直接 Key 值"],
                                    value=saved.key_mode,
                                    label="API Key 类型",
                                    elem_classes=["segmented-control"],
                                )
                                env_api_key = gr.Textbox(
                                    value=env_key_value,
                                    label="环境变量名",
                                    placeholder="例如：DEEPSEEK_API_KEY",
                                    info="填写环境变量名称。",
                                    visible=saved.key_mode == "环境变量",
                                )
                                direct_api_key_hidden = gr.Textbox(
                                    value=direct_key_value,
                                    label="直接 API Key",
                                    type="password",
                                    placeholder="请输入真实 API Key",
                                    info="默认不保存真实 Key。",
                                    visible=saved.key_mode == "直接 Key 值",
                                )
                                direct_api_key_visible = gr.Textbox(
                                    value=direct_key_value,
                                    label="直接 API Key",
                                    type="text",
                                    placeholder="请输入真实 API Key",
                                    info="当前为明文显示。",
                                    visible=False,
                                )
                                direct_key_visible = gr.State(False)
                                with gr.Row(elem_classes=["compact-row"]):
                                    show_direct_key_btn = gr.Button(
                                        "显示 Key",
                                        visible=saved.key_mode == "直接 Key 值",
                                        size="sm",
                                        elem_classes=["secondary-action", "compact-button"],
                                    )
                                    save_key = gr.Checkbox(value=saved.save_api_key, label="保存 API Key 到本地配置")
                                custom_prompt = gr.Textbox(
                                    value=saved.custom_prompt or DEFAULT_AI_PROMPT,
                                    label="AI 建议 Prompt",
                                    lines=7,
                                    max_lines=12,
                                )
                                with gr.Row(elem_classes=["compact-row"]):
                                    test_btn = gr.Button(
                                        "测试接口",
                                        elem_classes=["secondary-action", "compact-button"],
                                    )
                                test_result = gr.Textbox(label="测试反馈", interactive=False, lines=2)
                                with gr.Accordion("接口说明", open=False):
                                    gr.Markdown(
                                        "兼容 OpenAI Chat Completions。测试请求仅发送 `请只回复 OK`，"
                                        "字段限定为 `model`、`messages`、`temperature`、`max_tokens`。"
                                    )
                    with gr.Tab("对话记录"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>对话记录</h2><p>管理对话自动保存和数据目录。</p></div>')
                            auto_save = gr.Checkbox(value=saved.auto_save, label="自动保存对话记录")
                            save_history = gr.Checkbox(value=saved.save_history, label="自动保存检测历史")
                            history_limit = gr.Number(
                                value=saved.history_limit,
                                label="历史记录最多保留数量",
                                precision=0,
                                minimum=1,
                                maximum=1000,
                            )
                            with gr.Row(elem_classes=["path-row"]):
                                storage_dir = gr.Textbox(
                                    value=saved.storage_dir,
                                    label="存储目录",
                                    lines=1,
                                    max_lines=1,
                                    scale=8,
                                )
                                open_storage_btn = gr.Button(
                                    "...",
                                    size="sm",
                                    scale=1,
                                    elem_classes=["icon-action"],
                                )
                                default_storage_btn = gr.Button(
                                    "恢复默认",
                                    scale=2,
                                    elem_classes=["secondary-action"],
                                )
                            with gr.Accordion("帮助", open=False):
                                gr.Markdown(
                                    "对话、导出和病例记录会保存在该数据根目录下；更换目录后保存设置即可迁移。"
                                    "三点按钮会弹出路径选择器；开启自动保存后每次检测都会生成对话记录文件。"
                                    "检测历史默认只保存摘要和检测框，不保存原始上传图。"
                                )
                    with gr.Tab("高级接口"):
                        with gr.Group(elem_classes=["settings-card"]):
                            gr.HTML('<div class="section-heading"><h2>兼容接口</h2><p>用于接入兼容 OpenAI Chat Completions 的服务。</p></div>')
                            with gr.Accordion("查看接口说明", open=False):
                                gr.Markdown(
                                    "第一版固定使用 `/v1/chat/completions`，"
                                    "请求字段只使用 `model`、`messages`、`temperature`、`max_tokens`。"
                                )
                with gr.Row(elem_classes=["settings-actions"]):
                    save_settings_btn = gr.Button(
                        "保存设置",
                        variant="primary",
                        elem_classes=["primary-action", "compact-button"],
                    )
                settings_feedback = gr.HTML()

        common_inputs = [
            model_mode,
            primary_model_path,
            compare_model_path,
            conf,
            iou,
            device_choice,
            use_clahe,
            enable_compare,
            show_summary,
            ai_enabled,
            base_url,
            ai_model,
            key_mode,
            env_api_key,
            direct_api_key_hidden,
            direct_api_key_visible,
            direct_key_visible,
            save_key,
            auto_save,
            storage_dir,
            custom_prompt,
            advice_style,
            save_history,
            history_limit,
        ]
        common_outputs = [
            original_output,
            model_input_output,
            result_output,
            highres_result_output,
            crop_gallery,
            crop_status,
            result_image_file,
            result_image_path,
            download_result_btn,
            visible_class_filter,
            det_table,
            advice_box,
            quality_box,
            summary,
            batch_overview,
            batch_state,
            batch_select,
            chatbot,
            chat_state,
            batch_export_file,
            batch_export_path,
            export_batch_btn,
            batch_word_file,
            batch_word_path,
            export_batch_word_btn,
            export_file,
            export_path,
            word_report_file,
            word_report_path,
            export_word_btn,
            report_file,
            report_path,
            export_report_btn,
            save_case_btn,
        ]

        image.change(fn=clear_outputs_with_quality, inputs=image, outputs=common_outputs)
        batch_files.change(fn=clear_outputs, outputs=common_outputs)
        stale_result_controls = [primary_model_path, compare_model_path, conf, iou, device_choice, use_clahe]
        for control in stale_result_controls:
            control.change(fn=clear_outputs_with_quality, inputs=image, outputs=common_outputs)
        example_select.change(fn=_example_preview_text, inputs=example_select, outputs=example_info)
        load_example_btn.click(fn=load_demo_example, inputs=example_select, outputs=[image, example_info]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        run_btn.click(fn=run_single_detection, inputs=[image, *common_inputs], outputs=common_outputs)
        batch_btn.click(
            fn=run_batch_detection,
            inputs=[
                batch_files,
                model_mode,
                primary_model_path,
                compare_model_path,
                conf,
                iou,
                device_choice,
                use_clahe,
                enable_compare,
                show_summary,
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                env_api_key,
                direct_api_key_hidden,
                direct_api_key_visible,
                direct_key_visible,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
                advice_style,
                save_history,
                history_limit,
            ],
            outputs=common_outputs,
        )
        batch_select.change(
            fn=select_batch_item,
            inputs=[batch_select, batch_state, show_summary],
            outputs=[
                original_output,
                model_input_output,
                result_output,
                highres_result_output,
                crop_gallery,
                crop_status,
                result_image_file,
                result_image_path,
                download_result_btn,
                visible_class_filter,
                det_table,
                advice_box,
                quality_box,
                summary,
                chatbot,
                chat_state,
                export_file,
                export_path,
                word_report_file,
                word_report_path,
                export_word_btn,
                report_file,
                report_path,
                export_report_btn,
                save_case_btn,
            ],
        )
        visible_class_filter.change(
            fn=update_detection_visibility,
            inputs=[visible_class_filter, batch_select, batch_state],
            outputs=[
                result_output,
                highres_result_output,
                crop_gallery,
                crop_status,
                batch_state,
                det_table,
                result_image_file,
                result_image_path,
            ],
        )
        ai_enabled.change(fn=toggle_ai_settings, inputs=ai_enabled, outputs=ai_group)
        key_mode.change(
            fn=set_api_key_mode,
            inputs=key_mode,
            outputs=[env_api_key, direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        )
        show_direct_key_btn.click(
            fn=toggle_direct_key_visibility,
            inputs=[direct_api_key_hidden, direct_api_key_visible, direct_key_visible],
            outputs=[direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        )
        model_mode.change(fn=sync_model_mode, inputs=model_mode, outputs=[settings_model_mode, compare_model_path]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        settings_model_mode.change(fn=sync_model_mode, inputs=settings_model_mode, outputs=[model_mode, compare_model_path]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        enable_compare.change(
            fn=on_enable_compare_change,
            inputs=enable_compare,
            outputs=[model_mode, settings_model_mode, compare_model_path],
        ).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        show_summary.change(fn=toggle_summary, inputs=show_summary, outputs=summary)
        test_btn.click(
            fn=test_ai_settings,
            inputs=[
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                env_api_key,
                direct_api_key_hidden,
                direct_api_key_visible,
                direct_key_visible,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
                advice_style,
            ],
            outputs=test_result,
        )
        save_settings_btn.click(
            fn=save_ui_settings,
            inputs=[
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                env_api_key,
                direct_api_key_hidden,
                direct_api_key_visible,
                direct_key_visible,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
                advice_style,
                enable_compare,
                show_summary,
                settings_model_mode,
                model_dir,
                primary_model_path,
                compare_model_path,
                save_history,
                history_limit,
            ],
            outputs=[
                settings_feedback,
                case_select,
                case_table,
                case_detail,
                case_feedback,
                history_select,
                history_table,
                history_detail,
                history_feedback,
                case_report_file,
                case_report_path,
            ],
        )
        chat_btn.click(
            fn=continue_chat,
            inputs=[
                chat_input,
                chat_state,
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                env_api_key,
                direct_api_key_hidden,
                direct_api_key_visible,
                direct_key_visible,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
                advice_style,
            ],
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        chat_input.submit(
            fn=continue_chat,
            inputs=[
                chat_input,
                chat_state,
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                env_api_key,
                direct_api_key_hidden,
                direct_api_key_visible,
                direct_key_visible,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
                advice_style,
            ],
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        refresh_model_btn.click(
            fn=refresh_model_choices,
            inputs=[model_dir, model_file_select],
            outputs=[model_file_select, model_feedback],
        )
        open_model_dir_btn.click(
            fn=choose_model_dir,
            inputs=[model_dir, model_file_select],
            outputs=[model_dir, model_file_select, model_feedback],
        )
        apply_model_btn.click(
            fn=apply_selected_model,
            inputs=[model_file_select, model_apply_target],
            outputs=[primary_model_path, compare_model_path, model_cards_view, model_info_markdown, model_feedback],
        ).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        apply_model_card_btn.click(
            fn=apply_model_card,
            inputs=[model_card_select, model_dir],
            outputs=[primary_model_path, model_file_select, model_cards_view, model_info_markdown, model_feedback],
        ).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        test_model_btn.click(
            fn=test_model_file,
            inputs=[primary_model_path, compare_model_path, settings_model_mode],
            outputs=model_feedback,
        )
        default_storage_btn.click(fn=default_storage_dir, outputs=[storage_dir, settings_feedback])
        open_storage_btn.click(fn=choose_storage_dir, inputs=storage_dir, outputs=[storage_dir, settings_feedback])
        export_btn.click(fn=export_chat, inputs=[chat_state, storage_dir], outputs=[export_file, export_path])
        export_batch_btn.click(
            fn=export_batch_results,
            inputs=[batch_state, storage_dir],
            outputs=[batch_export_file, batch_export_path, batch_state],
        )
        export_batch_word_btn.click(
            fn=export_batch_word_report,
            inputs=[batch_state, storage_dir],
            outputs=[batch_word_file, batch_word_path, batch_state],
        )
        export_word_btn.click(
            fn=export_word_report,
            inputs=[batch_state, batch_select, storage_dir],
            outputs=[word_report_file, word_report_path, batch_state],
        )
        download_result_btn.click(
            fn=download_result_image,
            inputs=[batch_state, batch_select, storage_dir],
            outputs=[result_image_file, result_image_path],
        )
        export_report_btn.click(
            fn=export_single_report,
            inputs=[batch_state, batch_select, storage_dir],
            outputs=[report_file, report_path, batch_state],
        )
        save_case_btn.click(
            fn=save_case_record,
            inputs=[batch_state, batch_select, case_id, case_note, storage_dir],
            outputs=[case_feedback, case_select, case_table, case_detail, case_report_file, case_report_path],
        )
        refresh_case_btn.click(
            fn=refresh_case_records,
            inputs=storage_dir,
            outputs=[case_select, case_table, case_detail, case_feedback, case_report_file, case_report_path],
        )
        search_case_btn.click(
            fn=search_case_records_ui,
            inputs=[case_keyword, case_class_filter, case_level_filter, case_date_from, case_date_to, storage_dir],
            outputs=[case_select, case_table, case_detail, case_feedback, case_report_file, case_report_path],
        )
        delete_case_btn.click(
            fn=delete_selected_case_record,
            inputs=[
                case_select,
                case_keyword,
                case_class_filter,
                case_level_filter,
                case_date_from,
                case_date_to,
                storage_dir,
            ],
            outputs=[case_select, case_table, case_feedback, case_detail, case_report_file, case_report_path],
        )
        export_case_btn.click(
            fn=export_selected_case_record,
            inputs=[case_select, storage_dir],
            outputs=[case_report_file, case_report_path],
        )
        case_select.change(
            fn=load_case_record_and_clear_export,
            inputs=[case_select, storage_dir],
            outputs=[case_detail, case_report_file, case_report_path],
        )
        refresh_history_btn.click(
            fn=refresh_history_records,
            inputs=storage_dir,
            outputs=[history_select, history_table, history_detail, history_feedback],
        )
        history_select.change(
            fn=load_history_record,
            inputs=[history_select, storage_dir],
            outputs=history_detail,
        )
        delete_history_btn.click(
            fn=delete_selected_history_record,
            inputs=[history_select, storage_dir],
            outputs=[history_select, history_table, history_detail, history_feedback],
        )
        clear_history_btn.click(
            fn=clear_all_history_records,
            inputs=storage_dir,
            outputs=[history_select, history_table, history_detail, history_feedback],
        )

    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动牙齿病变区域识别 Gradio 应用。")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", default=7860, type=int)
    parser.add_argument("--share", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    missing = [
        str(info["path"]) for info in MODEL_REGISTRY.values() if not Path(info["path"]).exists()
    ]
    if missing:
        raise FileNotFoundError("模型文件不存在: " + "; ".join(missing))

    # 验证默认模型文件是否可被 YOLO 正常加载（捕获自定义模块缺失等）
    try:
        test_model = YOLO(str(DEFAULT_MODEL_PATH))
        print(f"[信息] 默认模型加载成功，类别：{test_model.names}")
    except Exception as exc:
        print(f"[警告] 默认模型加载失败：{exc}")
        print("  请确认自定义 YOLO 模块路径已配置，或切换到原始结构模型。")

    # 校验用户在设置中保存的模型路径是否存在
    saved = load_settings()
    user_model_issues = []
    for label, path_str in [
        ("主模型", saved.primary_model_path),
        ("对比模型", saved.compare_model_path),
    ]:
        if path_str and not Path(path_str).expanduser().exists():
            user_model_issues.append(f"{label}：{path_str}")
    if user_model_issues:
        print("[警告] 以下用户设置中的模型文件不存在：")
        for issue in user_model_issues:
            print(f"  - {issue}")
        print("  应用仍可启动，但使用这些模型前请在设置页重新选择有效模型文件。")

    args = parse_args()
    build_app().launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        theme=_workbench_theme(),
        css=_load_workbench_css(),
        js=_load_workbench_js(),
        allowed_paths=[str(root) for root in _allowed_file_roots()],
    )
