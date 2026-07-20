from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

import gradio as gr
import pandas as pd
import torch

from src.dental_detection.advice import default_advice, detection_prompt
from src.dental_detection.ai_client import chat_completion, normalize_base_url, test_chat_completion
from src.dental_detection.ai_defaults import (
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_KEY_ENV,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROMPT,
    SAFETY_NOTICE,
)
from src.dental_detection.conversation_store import save_conversation
from src.dental_detection.settings_store import (
    APP_HOME,
    AiSettings,
    CONFIG_PATH,
    case_dir,
    export_dir,
    load_settings,
    report_dir,
    save_settings,
    storage_root,
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
from src.dental_detection.gradio_files import (
    allowed_file_roots as _allowed_file_roots,
    clear_file_output as _clear_file_output,
    ensure_storage_root as _ensure_storage_root,
    file_component_output as _file_component_output,
    path_text as _path_text,
    remember_allowed_file_root as _remember_allowed_file_root,
    safe_existing_root as _safe_existing_root,
)
from src.dental_detection.error_messages import friendly_error_message
from src.dental_detection.exporters import (
    cleanup_payload_dir,
    create_zip_from_directory,
    ensure_export_dir,
    remove_empty_export_root,
    safe_export_stem,
    unique_export_root,
    write_csv_file,
    write_html_file,
    write_json_file,
    write_text_file,
    zip_path_for_root,
)
from src.dental_detection.image_quality import assess_image_quality_detail, format_quality_text
from src.dental_detection.inference import Detection, run_inference
from src.dental_detection.model_info import (
    build_model_cards,
    format_model_info_markdown,
    legend_html,
)
from src.dental_detection.model_files import (
    ADVANCED_MODEL_HINT,
    SUPPORTED_MODEL_DIR_SUFFIXES,
    SUPPORTED_MODEL_SUFFIXES,
    model_label_from_path,
    scan_model_files,
    supported_suffix_text,
)
from src.dental_detection.model_ui import (
    build_model_cards_html,
    build_workbench_model_status_html,
)
from src.dental_detection.patient_profile_ui import (
    add_patient_profile,
    archive_patient_profile,
    load_patient_profile_form,
    restore_patient_profile,
    sync_patient_selections,
    update_patient_profile,
)
from src.dental_detection.personal_workspace import (
    ensure_personal_workspace,
    personal_archived_patient_choices,
    personal_patient_choices,
    record_completed_detection,
    register_personal_report,
)
from src.dental_detection.report_center_ui import (
    build_report_center,
    load_report_center_item,
    refresh_report_center,
    trash_report_center_item,
)
from src.dental_detection.reporting import SingleReportData, export_batch_docx_report, export_single_docx_report
from src.dental_detection.record_formatters import format_case_record, format_history_record
from src.dental_detection.record_views import (
    case_choices_from_rows as _case_choices_from_rows,
    case_table_html as _case_table_html,
    history_choices_from_rows as _history_choices_from_rows,
    history_id as _history_id,
    history_table_html as _history_table_html,
)
from src.dental_detection.result_levels import enrich_detection_row, has_detection_payload, iter_detection_items
from src.dental_detection.result_items import (
    item_model_results,
    iter_model_result_items,
    model_result_detections,
    model_result_name,
    model_result_path,
)
from src.dental_detection.text_utils import json_safe_value, text_value
from src.dental_detection.ui_assets import load_workbench_css, load_workbench_js
from src.dental_detection.ui_contracts import (
    COMMON_OUTPUT_QUALITY_INDEX,
    common_input_components,
    common_output_components,
    common_output_values,
)
from src.dental_detection.ui_constants import (
    DETECTION_TABLE_COLUMNS,
    MODEL_MODE_COMPARE,
    MODEL_MODE_SINGLE,
    MODEL_SOURCE,
)
from src.dental_detection.ui_content import (
    AI_CHAT_INTRO_HTML,
    APP_HEADER_HTML,
    CASE_INTRO_HTML,
    section_heading,
)
from src.dental_detection.ui_settings_page import SettingsPageData, build_settings_page
from src.dental_detection.ui_workbench_page import WorkbenchPageData, build_workbench_page
from src.dental_detection.visualization import crop_detection_regions, draw_detections_with_filter, save_png_image, save_result_image
from src.dental_detection.workspace_store import WorkspaceError
from ultralytics import YOLO

EXAMPLE_DIR = PROJECT_ROOT / "assets" / "examples" / "dental"
EXAMPLE_META_PATH = EXAMPLE_DIR / "示例图片说明.json"
INFERENCE_CONCURRENCY_ID = "dental-inference"
CASE_UI_LIMIT = 200
HISTORY_UI_LIMIT = 200


def _workbench_theme():
    return gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="orange",
        neutral_hue="slate",
    )


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
        columns=DETECTION_TABLE_COLUMNS,
    )


def _table_from_detections(detections: list[Detection]) -> pd.DataFrame:
    rows = _clean_detection_records((det.as_row() for det in detections), image_size=None)
    return pd.DataFrame(rows, columns=DETECTION_TABLE_COLUMNS) if rows else _empty_table()


def _table_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = _clean_detection_records(records)
    return pd.DataFrame(rows, columns=DETECTION_TABLE_COLUMNS) if rows else _empty_table()


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


def _recommended_model_paths() -> set[str]:
    paths: set[str] = set()
    for info in MODEL_REGISTRY.values():
        try:
            paths.add(str(Path(info["path"]).expanduser().resolve()))
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            continue
    return paths


def refresh_model_choices(model_dir: str, current_value: str | None = None, include_advanced: bool = False):
    choices = scan_model_files(
        model_dir,
        include_advanced=bool(include_advanced),
        recommended_paths=_recommended_model_paths(),
    )
    # 保留用户已选模型，仅当原模型不在新列表中时才回退第一个
    value = current_value
    if value and not any(value == c[1] for c in choices):
        value = choices[0][1] if choices else None
    if not value:
        value = choices[0][1] if choices else None
    suffixes = supported_suffix_text()
    scope = "全部模型" if include_advanced else "推荐模型"
    message = f"已扫描到 {len(choices)} 个{scope}文件。" if choices else f"当前目录未发现{scope}（{suffixes}），请确认路径。"
    if include_advanced:
        message += f"\n{ADVANCED_MODEL_HINT}"
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
        build_model_cards_html(_model_cards(path), path),
        _current_model_info_markdown(path),
        f"已填入主模型：{path}",
    )


def _model_cards(selected_path: str | None = None) -> list[dict[str, Any]]:
    return build_model_cards(MODEL_REGISTRY)


def _workbench_model_status_html(selected_path: str | None) -> str:
    path = _model_path_or_default(selected_path, str(DEFAULT_MODEL_PATH))
    return build_workbench_model_status_html(
        path,
        _model_cards(path),
        default_model_path=str(DEFAULT_MODEL_PATH),
        recommended_paths=_recommended_model_paths(),
    )


def _model_card_choices() -> list[tuple[str, str]]:
    choices = []
    for card in _model_cards():
        suffix = str(card.get("status_text") or ("可用" if card.get("available") else "缺失"))
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


def apply_model_card(selected_path: str, model_dir: str | None = None, include_advanced: bool = False):
    if not selected_path:
        raise gr.Error("请先选择一个模型卡片。")
    card = next((item for item in _model_cards() if item.get("path") == selected_path), None)
    if not card:
        raise gr.Error("所选模型卡片无效，请刷新页面后重试。")
    if not card.get("available"):
        if card.get("status_text") == "依赖缺失":
            raise gr.Error("该模型所需的自定义运行模块缺失，请改用兼容模型或补齐项目依赖。")
        raise _friendly_gr_error(f"model file not found: {card.get('path')}", "模型文件不存在")
    path = str(Path(card["path"]).expanduser().resolve())
    choices = scan_model_files(
        _model_dir_or_default(model_dir),
        include_advanced=bool(include_advanced),
        recommended_paths=_recommended_model_paths(),
    )
    if not any(path == value for _, value in choices):
        choices = [(f"{model_label_from_path(path)}  |  {path}", path), *choices]
    return (
        gr.update(value=path),
        gr.update(choices=choices, value=path),
        build_model_cards_html(_model_cards(path), path),
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


def choose_model_dir(model_dir: str, current_value: str | None = None, include_advanced: bool = False):
    selected = _choose_directory_dialog("选择模型目录", model_dir or PROJECT_ROOT / "models")
    if not selected:
        return gr.update(), gr.update(), "未选择模型目录。"
    root = _safe_existing_root(selected)
    if root is None:
        return gr.update(), gr.update(), "选择的模型目录不可访问，请手动检查路径后重试。"
    path = str(root)
    choices = scan_model_files(
        path,
        include_advanced=bool(include_advanced),
        recommended_paths=_recommended_model_paths(),
    )
    value = current_value if current_value and any(current_value == c[1] for c in choices) else None
    value = value or (choices[0][1] if choices else None)
    suffixes = supported_suffix_text()
    scope = "全部模型" if include_advanced else "推荐模型"
    message = f"已选择模型目录：{path}。扫描到 {len(choices)} 个{scope}文件。"
    if not choices:
        message += f" 请确认该目录或其子目录中存在支持的模型文件（{suffixes}）。"
    if include_advanced:
        message += f"\n{ADVANCED_MODEL_HINT}"
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
        retain_limit = _normalize_history_limit(load_settings().history_limit)
        save_conversation(history, storage_dir, retain_limit=retain_limit)
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
    return safe_export_stem(name)


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


def _case_detail_from_choice(
    choice: str | None,
    storage_dir: str,
    patient_id: str | None = None,
) -> str:
    if not choice:
        return format_case_record(None)
    return load_case_record(choice, storage_dir, patient_id)


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
    write_text_file(path, content, encoding=encoding)


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
            f"<td>{_html_escape(det.get(key, ''))}</td>" for key in DETECTION_TABLE_COLUMNS
        )
        rows.append(f"<tr>{cells}</tr>")
    headers = "".join(f"<th>{name}</th>" for name in DETECTION_TABLE_COLUMNS)
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
    root = unique_export_root(report_dir(storage_dir), "single_report", stamp)
    return root, zip_path_for_root(root)


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
    export_root = unique_export_root(export_dir(storage_dir), "batch_result", stamp)
    return export_root, zip_path_for_root(export_root)


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
    ensure_export_dir(export_root)
    work_dir = export_root / "payload"
    images_dir = work_dir / "images"
    suggestions_dir = work_dir / "suggestions"
    ensure_export_dir(images_dir)
    ensure_export_dir(suggestions_dir)

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
                                **{key: det.get(key, "") for key in DETECTION_TABLE_COLUMNS},
                                "suggestion_type": suggestion_type,
                            }
                        )
                else:
                    csv_rows.append(
                        {
                            "image_name": name,
                            "display_name": display_name,
                            "model": model_name,
                            **{key: "" for key in DETECTION_TABLE_COLUMNS},
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

        write_csv_file(
            work_dir / "detections.csv",
            ["image_name", "display_name", "model", *DETECTION_TABLE_COLUMNS, "suggestion_type"],
            csv_rows,
        )

        write_json_file(
            work_dir / "detections.json",
            {"export": export_info, "overview": batch_overview, "items": json_items},
        )
        write_json_file(
            work_dir / "batch_overview.json",
            batch_overview,
        )
        write_json_file(
            work_dir / "批量检测总览.json",
            batch_overview,
        )
        _write_text(
            work_dir / "批量检测总览.csv",
            batch_overview_csv_text(batch_overview),
            encoding="utf-8-sig",
        )
        write_html_file(
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
        write_csv_file(
            work_dir / "class_stats.csv",
            ["类别", "中文名称", "检测框数量", "涉及图片数", "平均置信度", "最高置信度"],
            batch_overview.get("类别统计", []),
        )
        write_csv_file(
            work_dir / "focus_images.csv",
            ["排名", "图片名称", "最高类别", "原始类别", "最高置信度", "检测框数量", "关注等级"],
            batch_overview.get("重点关注图片", []),
        )
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

        create_zip_from_directory(zip_path, work_dir)
    finally:
        try:
            cleanup_payload_dir(work_dir)
        except OSError:
            pass  # 清理失败不掩盖导出成功
        try:
            remove_empty_export_root(export_root, zip_path)
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
    output_dir = unique_export_root(report_dir(storage_dir), "batch_word_report", stamp)
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
    ensure_export_dir(report_root)
    work_dir = report_root / "payload"
    images_dir = work_dir / "images"
    ensure_export_dir(images_dir)

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

        single_csv_rows: list[dict[str, Any]] = []
        for model_item in model_items:
            model = model_item["model"]
            model_detections = model_item["detections"]
            if model_detections:
                for det in model_detections:
                    single_csv_rows.append({"model": model, **{key: det.get(key, "") for key in DETECTION_TABLE_COLUMNS}})
            else:
                single_csv_rows.append({"model": model, **{key: "" for key in DETECTION_TABLE_COLUMNS}})
        write_csv_file(work_dir / "detections.csv", ["model", *DETECTION_TABLE_COLUMNS], single_csv_rows)

        write_json_file(
            work_dir / "detections.json",
            {
                    "report": export_info,
                    "summary": summary_data,
                    "models": model_items,
                    "detections": detections,
                    "image_files": image_files,
            },
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
        write_html_file(work_dir / "report.html", html)

        create_zip_from_directory(zip_path, work_dir)
    finally:
        try:
            cleanup_payload_dir(work_dir)
        except OSError:
            pass  # 清理失败不掩盖导出成功
        try:
            remove_empty_export_root(report_root, zip_path)
        except OSError:
            pass
    _sync_report_path(batch_state, [item], zip_path, "zip_report_path")
    update_history_report_paths([item], zip_path, storage_dir)
    workspace_warning = _register_workspace_report(item, zip_path, storage_dir, "zip")
    message = f"已导出单图报告：{zip_path}"
    if workspace_warning:
        message = f"{message}\n{workspace_warning}"
    return _file_component_output(zip_path), message, batch_state


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
    output_dir = unique_export_root(report_dir(storage_dir), "word_report", stamp, str(name))

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
    workspace_warning = _register_workspace_report(item, path, storage_dir, "docx")
    message = f"已导出 Word 报告：{path}"
    if workspace_warning:
        message = f"{message}\n{workspace_warning}"
    return _file_component_output(path), message, batch_state


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
        "patient_id": item.get("patient_id", ""),
        "task_id": item.get("task_id", ""),
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
    rows = list_case_records(storage_dir, item.get("patient_id"), limit=CASE_UI_LIMIT)
    choices = _case_choices_from_rows(rows)
    # 精确匹配：choices 格式为 "created_at | case_id | image_name | filename.json"
    selected = next(
        (choice for choice in choices if choice.split("|")[-1].strip() == path.name),
        choices[0] if choices else None,
    )
    return (
        f"病例记录已保存：{path}",
        gr.update(choices=choices, value=selected),
        _case_table_html(rows),
        format_case_record(payload),
        _clear_file_output(),
        "",
    )


def refresh_case_records(storage_dir: str, patient_id: str | None = None):
    _ensure_storage_root(storage_dir)
    rows = list_case_records(storage_dir, patient_id, limit=CASE_UI_LIMIT)
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _case_table_html(rows),
        _case_detail_from_choice(selected, storage_dir, patient_id),
        (
            f"已刷新病例记录，当前最多显示最近 {CASE_UI_LIMIT} 条。"
            if len(rows) >= CASE_UI_LIMIT
            else ("已刷新病例记录。" if choices else "暂无病例记录。")
        ),
        _clear_file_output(),
        "",
    )


def lazy_refresh_case_records(
    loaded: bool,
    storage_dir: str,
    patient_id: str | None = None,
):
    """Load the case archive once per browser session/tab lifecycle."""
    if loaded:
        return (*([gr.update()] * 6), True)
    return (*refresh_case_records(storage_dir, patient_id), True)


def search_case_records_ui(
    keyword: str,
    class_filter: str,
    level_filter: str,
    date_from: str,
    date_to: str,
    storage_dir: str,
    patient_id: str | None = None,
):
    _ensure_storage_root(storage_dir)
    date_from, date_to = _validate_case_date_filters(date_from, date_to)
    rows = search_case_records(
        storage_dir,
        keyword,
        class_filter,
        level_filter,
        date_from,
        date_to,
        patient_id,
        limit=CASE_UI_LIMIT,
    )
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    message = (
        f"已显示前 {CASE_UI_LIMIT} 条匹配病例，请继续缩小筛选范围。"
        if len(rows) >= CASE_UI_LIMIT
        else (f"已筛选到 {len(rows)} 条病例记录。" if rows else "未找到匹配病例记录。")
    )
    return (
        gr.update(choices=choices, value=selected),
        _case_table_html(rows),
        _case_detail_from_choice(selected, storage_dir, patient_id),
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
    patient_id: str | None = None,
):
    if not choice:
        raise gr.Error("请先选择要移入回收站的病例记录。")
    _ensure_storage_root(storage_dir)
    date_from, date_to = _validate_case_date_filters(date_from, date_to)
    file_name = _case_file_name_from_choice(choice)
    try:
        trash_path = move_case_to_trash(storage_dir, file_name, patient_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise gr.Error(str(exc)) from exc
    rows = search_case_records(
        storage_dir,
        keyword,
        class_filter,
        level_filter,
        date_from,
        date_to,
        patient_id,
        limit=CASE_UI_LIMIT,
    )
    choices = _case_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _case_table_html(rows),
        f"病例已移入回收站：{trash_path}",
        _case_detail_from_choice(selected, storage_dir, patient_id),
        _clear_file_output(),
        "",
    )


def export_selected_case_record(
    choice: str,
    storage_dir: str,
    patient_id: str | None = None,
):
    if not choice:
        raise gr.Error("请先选择要导出的病例记录。")
    _ensure_storage_root(storage_dir)
    file_name = _case_file_name_from_choice(choice)
    try:
        path = export_case_report(storage_dir, file_name, patient_id)
    except (OSError, UnicodeDecodeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise gr.Error(f"病例文件损坏或无法读取：{exc}") from exc
    _remember_allowed_file_root(path.parent)
    return _file_component_output(path), f"已导出病例报告：{path}"


def load_case_record(
    choice: str,
    storage_dir: str,
    patient_id: str | None = None,
):
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
        return format_case_record(load_case_record_data(storage_dir, file_name, patient_id))
    except (OSError, UnicodeDecodeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        return format_case_record({"错误": f"病例文件损坏或无法读取：{exc}"})


def load_case_record_and_clear_export(
    choice: str,
    storage_dir: str,
    patient_id: str | None = None,
):
    return load_case_record(choice, storage_dir, patient_id), _clear_file_output(), ""


def refresh_history_records(storage_dir: str, patient_id: str | None = None):
    _ensure_storage_root(storage_dir)
    rows = history_rows(storage_dir, patient_id, limit=HISTORY_UI_LIMIT)
    choices = _history_choices_from_rows(rows)
    selected = choices[0] if choices else None
    return (
        gr.update(choices=choices, value=selected),
        _history_table_html(rows),
        load_history_record(selected, storage_dir, patient_id) if selected else format_history_record(None),
        (
            f"历史记录已刷新，当前最多显示最近 {HISTORY_UI_LIMIT} 条。"
            if len(rows) >= HISTORY_UI_LIMIT
            else ("历史记录已刷新。" if choices else "暂无检测历史。")
        ),
    )


def lazy_refresh_history_page(
    loaded: bool,
    storage_dir: str,
    patient_id: str | None = None,
):
    """Load history and reports once; explicit refresh buttons remain available."""
    if loaded:
        return (*([gr.update()] * 10), True)
    return (
        *refresh_history_records(storage_dir, patient_id),
        *refresh_report_center(storage_dir, patient_id),
        True,
    )


def refresh_report_center_after_storage_change(
    storage_changed: bool,
    storage_dir: str,
    patient_id: str,
):
    if not storage_changed:
        return tuple(gr.update() for _ in range(6))
    return refresh_report_center(storage_dir, patient_id)


def load_history_record(choice: str, storage_dir: str, patient_id: str | None = None) -> str:
    try:
        _ensure_storage_root(storage_dir)
    except gr.Error as exc:
        return str(exc)
    return format_history_record(load_history_record_data(_history_id(choice), storage_dir, patient_id))


def delete_selected_history_record(choice: str, storage_dir: str, patient_id: str | None = None):
    _ensure_storage_root(storage_dir)
    record_id = _history_id(choice)
    if not record_id:
        history_select, table, detail, message = refresh_history_records(storage_dir, patient_id)
        return history_select, table, detail, "请选择要删除的历史记录。"
    deleted = delete_history_record(record_id, storage_dir, patient_id)
    history_select, table, detail, message = refresh_history_records(storage_dir, patient_id)
    feedback = "已删除所选历史记录。" if deleted else "未找到所选历史记录，请刷新后重试。"
    return history_select, table, detail, feedback or message


def clear_all_history_records(storage_dir: str, patient_id: str | None = None):
    _ensure_storage_root(storage_dir)
    clear_history_records(storage_dir, patient_id)
    return (
        gr.update(choices=[], value=None),
        _history_table_html([]),
        "请选择一条检测历史。",
        "当前患者的检测历史已清空。病例记录不会被删除。",
    )


def clear_outputs():
    return common_output_values(
        {
            "original": None,
            "model_input": None,
            "result": None,
            "highres_result": None,
            "crop_gallery": [],
            "crop_status": "暂无疑似区域局部图",
            "result_image_file": _clear_file_output(),
            "result_image_path": "",
            "download_result_button": gr.update(value="下载检测结果图", interactive=False),
            "visible_class_filter": gr.update(choices=[], value=[], interactive=False),
            "detection_table": _empty_table(),
            "advice": "",
            "quality": "等待上传图像",
            "summary": gr.update(value={}, visible=False),
            "batch_overview": gr.update(value="", visible=False),
            "batch_state": [],
            "batch_select": gr.update(choices=[], value=None),
            "chatbot": gr.update(),
            "chat_state": gr.update(),
            "batch_export_file": _clear_file_output(),
            "batch_export_path": "",
            "batch_export_button": gr.update(interactive=False),
            "batch_word_file": _clear_file_output(),
            "batch_word_path": "",
            "batch_word_button": gr.update(interactive=False),
            "chat_export_file": _clear_file_output(),
            "chat_export_path": "",
            "word_report_file": _clear_file_output(),
            "word_report_path": "",
            "word_export_button": gr.update(value="导出 Word 报告", interactive=False),
            "zip_report_file": _clear_file_output(),
            "zip_report_path": "",
            "zip_export_button": gr.update(value="导出 ZIP 数据包", interactive=False),
            "save_case_button": gr.update(value="完成检测后可保存", interactive=False),
        }
    )


def clear_outputs_with_quality(image):
    values = list(clear_outputs())
    values[COMMON_OUTPUT_QUALITY_INDEX] = assess_image_quality(image)
    return tuple(values)


def clear_patient_session():
    return (None, None, *clear_outputs(), "", "")


def _record_workspace_detection(
    storage_dir: str,
    patient_id: str,
    selected_models: list[tuple[str, str]],
    *,
    parameters: dict[str, Any],
    result: dict[str, Any],
    quality_level: str,
) -> tuple[str, str]:
    detections = _clean_detection_records(result.get("detections", []))
    classes = sorted(
        {
            str(row.get("中文名称") or row.get("class") or "未知类别")
            for row in detections
        }
    )
    try:
        task = record_completed_detection(
            storage_dir,
            patient_id,
            "、".join(name for name, _ in selected_models),
            parameters=json_safe_value(parameters),
            result_summary=json_safe_value(
                {
                    "detection_count": len(detections),
                    "classes": classes,
                    "quality_level": quality_level,
                    "models": [name for name, _ in selected_models],
                }
            ),
        )
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        message = friendly_error_message(exc, "检测任务记录保存失败").splitlines()[0]
        return "", f"检测已经完成，但未能保存到患者档案：{message}"
    return task.id, ""


def _register_workspace_report(
    item: dict[str, Any],
    report_path: str | Path,
    storage_dir: str,
    report_format: str,
) -> str:
    patient_id = str(item.get("patient_id") or "").strip()
    task_id = str(item.get("task_id") or "").strip()
    if not patient_id or not task_id:
        return ""
    models = [model_result_name(result) for result in _item_results(item)]
    model_version = "、".join(model for model in models if model)
    try:
        report = register_personal_report(
            storage_dir,
            patient_id,
            task_id,
            report_path,
            report_format=report_format,
            model_version=model_version,
        )
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        message = friendly_error_message(exc, "报告记录保存失败").splitlines()[0]
        return f"报告文件已生成，但未能写入患者档案：{message}"
    report_assets = item.setdefault("report_asset_ids", {})
    if isinstance(report_assets, dict):
        report_assets[report_format] = report.id
    return ""


def run_single_detection(
    image,
    model_mode: str,
    patient_id: str,
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
    task_id, workspace_warning = _record_workspace_detection(
        settings.storage_dir,
        patient_id,
        selected_models,
        parameters={
            "model_mode": model_mode if enable_compare else MODEL_MODE_SINGLE,
            "conf": conf,
            "iou": iou,
            "device": device_choice,
            "use_clahe": bool(use_clahe),
        },
        result=primary,
        quality_level=quality_level,
    )
    if workspace_warning:
        advice = f"{advice}\n\n{workspace_warning}"
        chat_history = _conversation_from_advice(advice)

    batch_state = [
        {
            "name": "当前单图",
            "task_id": task_id,
            "patient_id": patient_id,
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
    return common_output_values(
        {
            "original": primary["original"],
            "model_input": primary["model_input"],
            "result": primary["annotated"],
            "highres_result": highres_image,
            "crop_gallery": crop_items,
            "crop_status": crop_text,
            "result_image_file": _clear_file_output(),
            "result_image_path": "",
            "download_result_button": gr.update(value="下载检测结果图", interactive=True),
            "visible_class_filter": _visible_class_update(primary),
            "detection_table": primary["table"],
            "advice": advice,
            "quality": quality_text,
            "summary": gr.update(value=summary, visible=show_summary),
            "batch_overview": gr.update(value="", visible=False),
            "batch_state": batch_state,
            "batch_select": gr.update(choices=["当前单图"], value="当前单图"),
            "chatbot": chat_history,
            "chat_state": chat_history,
            "batch_export_file": _clear_file_output(),
            "batch_export_path": "",
            "batch_export_button": gr.update(interactive=False),
            "batch_word_file": _clear_file_output(),
            "batch_word_path": "",
            "batch_word_button": gr.update(interactive=False),
            "chat_export_file": _clear_file_output(),
            "chat_export_path": "",
            "word_report_file": _clear_file_output(),
            "word_report_path": "",
            "word_export_button": gr.update(value="导出 Word 报告", interactive=True),
            "zip_report_file": _clear_file_output(),
            "zip_report_path": "",
            "zip_export_button": gr.update(value="导出 ZIP 数据包", interactive=True),
            "save_case_button": gr.update(value="保存病例", interactive=True),
        }
    )


def _file_name(file_obj) -> str:
    path = getattr(file_obj, "name", None) or str(file_obj)
    return Path(path).name


def run_batch_detection(
    files,
    model_mode: str,
    patient_id: str,
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
    workspace_warnings: list[str] = []
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
        item_summary = {
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
        }
        task_id, workspace_warning = _record_workspace_detection(
            settings.storage_dir,
            patient_id,
            selected_models,
            parameters={
                "model_mode": model_mode if enable_compare else MODEL_MODE_SINGLE,
                "conf": conf,
                "iou": iou,
                "device": device_choice,
                "use_clahe": bool(use_clahe),
                "file_name": file_name,
            },
            result=result,
            quality_level=quality_level,
        )
        if workspace_warning:
            workspace_warnings.append(f"{file_name}：{workspace_warning}")
        batch_state.append(
            {
                "name": file_name,
                "display_name": f"{index:03d} - {file_name}",
                "task_id": task_id,
                "patient_id": patient_id,
                "result": result,
                "all_results": all_results,
                "advice": advice,
                "suggestion_type": _suggestion_type(settings.enabled),
                "quality_text": quality_text,
                "quality_level": quality_level,
                "summary": item_summary,
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
    if workspace_warnings:
        first["advice"] = f"{first['advice']}\n\n" + "\n".join(workspace_warnings[:5])
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
    return common_output_values(
        {
            "original": first["result"]["original"],
            "model_input": first["result"]["model_input"],
            "result": first["result"]["annotated"],
            "highres_result": highres_image,
            "crop_gallery": crop_items,
            "crop_status": crop_text,
            "result_image_file": _clear_file_output(),
            "result_image_path": "",
            "download_result_button": gr.update(value="下载检测结果图", interactive=True),
            "visible_class_filter": _visible_class_update(first["result"]),
            "detection_table": first["result"]["table"],
            "advice": first["advice"],
            "quality": first.get("quality_text") or assess_image_quality(first["result"]["original"]),
            "summary": gr.update(value=first["summary"], visible=show_summary),
            "batch_overview": gr.update(value=batch_overview_html(overview), visible=True),
            "batch_state": batch_state,
            "batch_select": gr.update(choices=choices, value=choices[0]),
            "chatbot": chat_history,
            "chat_state": chat_history,
            "batch_export_file": _clear_file_output(),
            "batch_export_path": "",
            "batch_export_button": gr.update(interactive=True),
            "batch_word_file": _clear_file_output(),
            "batch_word_path": "",
            "batch_word_button": gr.update(interactive=True),
            "chat_export_file": _clear_file_output(),
            "chat_export_path": "",
            "word_report_file": _clear_file_output(),
            "word_report_path": "",
            "word_export_button": gr.update(value="导出 Word 报告", interactive=True),
            "zip_report_file": _clear_file_output(),
            "zip_report_path": "",
            "zip_export_button": gr.update(value="导出 ZIP 数据包", interactive=True),
            "save_case_button": gr.update(value="保存病例", interactive=True),
        }
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
    previous_settings = load_settings()
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
        # Switching the active data root must stay a fast, non-destructive
        # settings operation. Bulk migration remains an explicit helper.
        path = save_settings(settings, migrate_data=False)
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
    try:
        storage_changed = storage_root(previous_settings.storage_dir).resolve() != storage_root(
            settings.storage_dir
        ).resolve()
    except (OSError, RuntimeError, ValueError):
        storage_changed = previous_settings.storage_dir != settings.storage_dir
    if storage_changed:
        feedback.append("数据目录已切换；旧目录内容未自动搬移。")
    if not storage_changed:
        # Saving model/AI preferences must not rescan the case and history
        # archives. Existing selectors remain valid and explicit refresh
        # buttons or tab entry will load records when needed.
        return (
            _toast("\n".join(feedback), "success"),
            *([gr.update()] * 20),
            False,
        )
    try:
        workspace = ensure_personal_workspace(settings.storage_dir)
        patient_choices = personal_patient_choices(settings.storage_dir)
        archived_choices = personal_archived_patient_choices(settings.storage_dir)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _friendly_gr_error(exc, "患者工作区初始化失败") from exc
    # The new root is intentionally presented empty here; the record tabs
    # populate themselves lazily on first navigation.
    case_choices: list[tuple[str, str]] = []
    history_choices: list[tuple[str, str]] = []
    case_message = "当前存储位置暂无病例记录。"
    history_message = "当前存储位置暂无检测历史。"
    return (
        _toast("\n".join(feedback), "success"),
        gr.update(choices=case_choices, value=None),
        _case_table_html([]),
        _case_detail_from_choice(None, settings.storage_dir, workspace.patient.id),
        case_message,
        gr.update(choices=history_choices, value=None),
        _history_table_html([]),
        format_history_record(None),
        history_message,
        _clear_file_output(),
        "",
        gr.update(choices=patient_choices, value=workspace.patient.id),
        gr.update(choices=patient_choices, value=workspace.patient.id),
        gr.update(choices=patient_choices, value=workspace.patient.id),
        gr.update(
            choices=archived_choices,
            value=archived_choices[0][1] if archived_choices else None,
        ),
        workspace.patient.display_name,
        workspace.patient.external_reference,
        gr.update(interactive=False),
        gr.update(interactive=bool(archived_choices)),
        False,
        False,
        True,
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


def clear_current_chat():
    return [], [], "", _clear_file_output(), ""


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
    personal_workspace = ensure_personal_workspace(saved.storage_dir)
    patient_choices = personal_patient_choices(saved.storage_dir)
    archived_patient_choices = personal_archived_patient_choices(saved.storage_dir)
    env_key_value, direct_key_value = _api_key_inputs(saved)
    model_choices = scan_model_files(
        saved.model_dir,
        include_advanced=False,
        recommended_paths=_recommended_model_paths(),
    )
    model_choice_values = {value for _, value in model_choices}
    # Record stores are intentionally loaded on first navigation instead of
    # during app construction. Large personal data roots must not block the
    # Gradio page from becoming interactive.
    initial_case_rows: list[dict[str, Any]] = []
    initial_history_rows: list[dict[str, Any]] = []
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
        case_loaded_state = gr.State(False)
        history_loaded_state = gr.State(False)
        storage_changed_state = gr.State(False)
        gr.HTML(APP_HEADER_HTML)

        with gr.Tabs(elem_classes=["main-tabs"]):
            with gr.Tab("检测工作台"):
                workbench = build_workbench_page(
                    WorkbenchPageData(
                        saved=saved,
                        model_status_html=_workbench_model_status_html(saved_primary_model_path),
                        patient_choices=patient_choices,
                        selected_patient_id=personal_workspace.patient.id,
                        example_choices=_example_choices(),
                        device_choices=device_choices,
                        default_device_choice=_default_device_choice(),
                        initial_detection_table=_empty_table(),
                    )
                )
            with gr.Tab("AI 问答"):
                with gr.Group(elem_classes=["section-card", "chat-card"]):
                    gr.HTML(AI_CHAT_INTRO_HTML)
                    with gr.Row(elem_classes=["chat-toolbar"]):
                        clear_chat_btn = gr.Button(
                            "新建对话",
                            elem_classes=["secondary-action", "compact-button"],
                        )
                    chatbot = gr.Chatbot(
                        label="问答记录",
                        show_label=False,
                        height=420,
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

            with gr.Tab("病例记录") as case_tab:
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML(CASE_INTRO_HTML)
                    case_patient_select = gr.Dropdown(
                        label="当前患者档案",
                        choices=patient_choices,
                        value=personal_workspace.patient.id,
                    )
                    with gr.Accordion("添加患者档案", open=False, elem_classes=["compact-accordion"]):
                        with gr.Row(elem_classes=["compact-row"]):
                            new_patient_name = gr.Textbox(
                                label="档案名称",
                                placeholder="例如：本人、儿童或家人",
                                lines=1,
                                max_lines=1,
                            )
                            new_patient_reference = gr.Textbox(
                                label="档案编号（可选）",
                                placeholder="例如：P-002",
                                lines=1,
                                max_lines=1,
                            )
                            add_patient_btn = gr.Button(
                                "添加档案",
                                elem_classes=["secondary-action", "compact-button"],
                            )
                    with gr.Accordion("管理当前档案", open=False, elem_classes=["compact-accordion"]):
                        with gr.Row(elem_classes=["compact-row"]):
                            edit_patient_name = gr.Textbox(
                                value=personal_workspace.patient.display_name,
                                label="档案名称",
                                lines=1,
                                max_lines=1,
                            )
                            edit_patient_reference = gr.Textbox(
                                value=personal_workspace.patient.external_reference,
                                label="档案编号（可选）",
                                lines=1,
                                max_lines=1,
                            )
                        with gr.Row(elem_classes=["compact-row"]):
                            save_patient_btn = gr.Button(
                                "保存档案",
                                elem_classes=["secondary-action", "compact-button"],
                            )
                            archive_patient_btn = gr.Button(
                                "归档当前档案",
                                interactive=False,
                                elem_classes=["secondary-action", "compact-button"],
                            )
                    with gr.Accordion("恢复已归档档案", open=False, elem_classes=["compact-accordion"]):
                        with gr.Row(elem_classes=["compact-row"]):
                            archived_patient_select = gr.Dropdown(
                                label="已归档档案",
                                choices=archived_patient_choices,
                                value=archived_patient_choices[0][1] if archived_patient_choices else None,
                            )
                            restore_patient_btn = gr.Button(
                                "恢复档案",
                                interactive=bool(archived_patient_choices),
                                elem_classes=["secondary-action", "compact-button"],
                            )
                    patient_feedback = gr.HTML()
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
                    case_feedback = gr.Textbox(
                        label="病例反馈",
                        interactive=False,
                        lines=1,
                        elem_classes=["inline-feedback"],
                    )
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML(
                        '<div class="section-heading"><h2>已保存病例</h2>'
                        '<p>选择记录后查看结构化详情；暂无记录时可先完成一次检测并点击保存病例。</p></div>'
                    )
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
                    with gr.Accordion(
                        "结构化病例列表",
                        open=False,
                        elem_classes=["compact-accordion"],
                    ):
                        case_table = gr.HTML(
                            value=_case_table_html(initial_case_rows),
                            elem_classes=["record-table-shell"],
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

            with gr.Tab("检测历史") as history_tab:
                with gr.Group(elem_classes=["section-card", "case-card"]):
                    gr.HTML(
                        '<div class="card-heading"><div><h2>检测历史</h2>'
                        '<p>自动保存最近检测摘要，默认不保存原始上传图。</p></div></div>'
                    )
                    history_patient_select = gr.Dropdown(
                        label="当前患者档案",
                        choices=patient_choices,
                        value=personal_workspace.patient.id,
                    )
                    with gr.Row(elem_classes=["compact-row"]):
                        refresh_history_btn = gr.Button("刷新历史", elem_classes=["secondary-action", "compact-button"])
                        delete_history_btn = gr.Button("删除所选", elem_classes=["secondary-action", "compact-button"])
                        clear_history_btn = gr.Button("清空历史", elem_classes=["secondary-action", "compact-button"])
                    history_feedback = gr.Textbox(
                        label="历史反馈",
                        interactive=False,
                        lines=1,
                        elem_classes=["inline-feedback"],
                    )
                    history_select = gr.Dropdown(
                        label="检测历史",
                        choices=_history_choices_from_rows(initial_history_rows),
                    )
                    with gr.Accordion(
                        "结构化历史列表",
                        open=False,
                        elem_classes=["compact-accordion"],
                    ):
                        history_table = gr.HTML(
                            value=_history_table_html(initial_history_rows),
                            elem_classes=["record-table-shell"],
                        )
                    history_detail = gr.Textbox(
                        value=format_history_record(None),
                        label="历史详情",
                        interactive=False,
                        lines=14,
                    )
                report_center = build_report_center(
                    saved.storage_dir,
                    personal_workspace.patient.id,
                    load_initial=False,
                )

            with gr.Tab("设置"):
                settings = build_settings_page(
                    SettingsPageData(
                        saved=saved,
                        primary_model_path=saved_primary_model_path,
                        model_cards_html=build_model_cards_html(
                            _model_cards(saved_primary_model_path),
                            saved_primary_model_path,
                        ),
                        model_card_choices=model_card_choices,
                        model_choices=model_choices,
                        selected_model_choice=selected_model_choice,
                        model_dir=_model_dir_or_default(saved.model_dir),
                        compare_model_path=_model_path_or_default(
                            saved.compare_model_path,
                            str(MODEL_REGISTRY[MODEL_SOURCE]["path"]),
                        ),
                        model_info_markdown=_current_model_info_markdown(saved_primary_model_path),
                        env_api_key=env_key_value,
                        direct_api_key=direct_key_value,
                    )
                )

        workbench_model_status = workbench.workbench_model_status
        patient_select = workbench.patient_select
        clear_session_btn = workbench.clear_session_btn
        image = workbench.image
        run_btn = workbench.run_btn
        example_select = workbench.example_select
        load_example_btn = workbench.load_example_btn
        example_info = workbench.example_info
        batch_files = workbench.batch_files
        batch_btn = workbench.batch_btn
        batch_select = workbench.batch_select
        export_batch_btn = workbench.export_batch_btn
        export_batch_word_btn = workbench.export_batch_word_btn
        batch_export_file = workbench.batch_export_file
        batch_word_file = workbench.batch_word_file
        batch_export_path = workbench.batch_export_path
        batch_word_path = workbench.batch_word_path
        batch_overview = workbench.batch_overview
        model_mode = workbench.model_mode
        device_choice = workbench.device_choice
        conf = workbench.conf
        iou = workbench.iou
        use_clahe = workbench.use_clahe
        original_output = workbench.original_output
        model_input_output = workbench.model_input_output
        result_output = workbench.result_output
        highres_result_output = workbench.highres_result_output
        crop_status = workbench.crop_status
        crop_gallery = workbench.crop_gallery
        result_image_path = workbench.result_image_path
        download_result_btn = workbench.download_result_btn
        result_image_file = workbench.result_image_file
        visible_class_filter = workbench.visible_class_filter
        det_table = workbench.det_table
        advice_box = workbench.advice_box
        quality_box = workbench.quality_box
        summary = workbench.summary
        word_report_path = workbench.word_report_path
        export_word_btn = workbench.export_word_btn
        word_report_file = workbench.word_report_file
        report_path = workbench.report_path
        export_report_btn = workbench.export_report_btn
        report_file = workbench.report_file

        enable_compare = settings.enable_compare
        show_summary = settings.show_summary
        model_cards_view = settings.model_cards_view
        model_card_select = settings.model_card_select
        apply_model_card_btn = settings.apply_model_card_btn
        settings_model_mode = settings.settings_model_mode
        show_advanced_models = settings.show_advanced_models
        model_dir = settings.model_dir
        open_model_dir_btn = settings.open_model_dir_btn
        refresh_model_btn = settings.refresh_model_btn
        model_file_select = settings.model_file_select
        apply_model_btn = settings.apply_model_btn
        model_apply_target = settings.model_apply_target
        primary_model_path = settings.primary_model_path
        compare_model_path = settings.compare_model_path
        test_model_btn = settings.test_model_btn
        model_feedback = settings.model_feedback
        model_info_markdown = settings.model_info_markdown
        ai_enabled = settings.ai_enabled
        advice_style = settings.advice_style
        ai_group = settings.ai_group
        ai_model = settings.ai_model
        base_url = settings.base_url
        key_mode = settings.key_mode
        env_api_key = settings.env_api_key
        direct_api_key_hidden = settings.direct_api_key_hidden
        direct_api_key_visible = settings.direct_api_key_visible
        direct_key_visible = settings.direct_key_visible
        show_direct_key_btn = settings.show_direct_key_btn
        save_key = settings.save_key
        custom_prompt = settings.custom_prompt
        test_btn = settings.test_btn
        test_result = settings.test_result
        auto_save = settings.auto_save
        save_history = settings.save_history
        history_limit = settings.history_limit
        storage_dir = settings.storage_dir
        open_storage_btn = settings.open_storage_btn
        default_storage_btn = settings.default_storage_btn
        save_settings_btn = settings.save_settings_btn
        settings_feedback = settings.settings_feedback
        common_inputs = common_input_components(workbench.common_input_map(settings))
        common_outputs = common_output_components(
            {
                "original": original_output,
                "model_input": model_input_output,
                "result": result_output,
                "highres_result": highres_result_output,
                "crop_gallery": crop_gallery,
                "crop_status": crop_status,
                "result_image_file": result_image_file,
                "result_image_path": result_image_path,
                "download_result_button": download_result_btn,
                "visible_class_filter": visible_class_filter,
                "detection_table": det_table,
                "advice": advice_box,
                "quality": quality_box,
                "summary": summary,
                "batch_overview": batch_overview,
                "batch_state": batch_state,
                "batch_select": batch_select,
                "chatbot": chatbot,
                "chat_state": chat_state,
                "batch_export_file": batch_export_file,
                "batch_export_path": batch_export_path,
                "batch_export_button": export_batch_btn,
                "batch_word_file": batch_word_file,
                "batch_word_path": batch_word_path,
                "batch_word_button": export_batch_word_btn,
                "chat_export_file": export_file,
                "chat_export_path": export_path,
                "word_report_file": word_report_file,
                "word_report_path": word_report_path,
                "word_export_button": export_word_btn,
                "zip_report_file": report_file,
                "zip_report_path": report_path,
                "zip_export_button": export_report_btn,
                "save_case_button": save_case_btn,
            }
        )
        case_list_outputs = [
            case_select,
            case_table,
            case_detail,
            case_feedback,
            case_report_file,
            case_report_path,
        ]
        history_list_outputs = [history_select, history_table, history_detail, history_feedback]
        report_list_outputs = [
            report_center.report_select,
            report_center.report_table,
            report_center.report_detail,
            report_center.report_file,
            report_center.report_feedback,
            report_center.trash_button,
        ]

        # Lazy-load record stores when their tabs become visible. This keeps
        # startup and tab navigation responsive even with large local archives.
        case_tab.select(
            fn=lazy_refresh_case_records,
            inputs=[case_loaded_state, storage_dir, case_patient_select],
            outputs=[*case_list_outputs, case_loaded_state],
        )
        history_tab.select(
            fn=lazy_refresh_history_page,
            inputs=[history_loaded_state, storage_dir, history_patient_select],
            outputs=[*history_list_outputs, *report_list_outputs, history_loaded_state],
        )

        clear_session_btn.click(
            fn=clear_patient_session,
            outputs=[image, batch_files, *common_outputs, case_id, case_note],
        )
        patient_select.input(
            fn=sync_patient_selections,
            inputs=patient_select,
            outputs=[case_patient_select, history_patient_select],
        ).then(fn=clear_patient_session, outputs=[image, batch_files, *common_outputs, case_id, case_note]).then(
            fn=refresh_case_records,
            inputs=[storage_dir, patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=load_patient_profile_form,
            inputs=[patient_select, storage_dir],
            outputs=[edit_patient_name, edit_patient_reference, archive_patient_btn],
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, patient_select],
            outputs=report_list_outputs,
        )
        case_patient_select.input(
            fn=sync_patient_selections,
            inputs=case_patient_select,
            outputs=[patient_select, history_patient_select],
        ).then(fn=clear_patient_session, outputs=[image, batch_files, *common_outputs, case_id, case_note]).then(
            fn=refresh_case_records,
            inputs=[storage_dir, case_patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, case_patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=load_patient_profile_form,
            inputs=[case_patient_select, storage_dir],
            outputs=[edit_patient_name, edit_patient_reference, archive_patient_btn],
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, case_patient_select],
            outputs=report_list_outputs,
        )
        history_patient_select.input(
            fn=sync_patient_selections,
            inputs=history_patient_select,
            outputs=[patient_select, case_patient_select],
        ).then(fn=clear_patient_session, outputs=[image, batch_files, *common_outputs, case_id, case_note]).then(
            fn=refresh_case_records,
            inputs=[storage_dir, history_patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, history_patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=load_patient_profile_form,
            inputs=[history_patient_select, storage_dir],
            outputs=[edit_patient_name, edit_patient_reference, archive_patient_btn],
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, history_patient_select],
            outputs=report_list_outputs,
        )
        add_patient_btn.click(
            fn=add_patient_profile,
            inputs=[new_patient_name, new_patient_reference, storage_dir],
            outputs=[
                patient_select,
                case_patient_select,
                history_patient_select,
                new_patient_name,
                new_patient_reference,
                patient_feedback,
            ],
        ).then(fn=clear_patient_session, outputs=[image, batch_files, *common_outputs, case_id, case_note]).then(
            fn=refresh_case_records,
            inputs=[storage_dir, case_patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, case_patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=load_patient_profile_form,
            inputs=[case_patient_select, storage_dir],
            outputs=[edit_patient_name, edit_patient_reference, archive_patient_btn],
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, case_patient_select],
            outputs=report_list_outputs,
        )
        save_patient_btn.click(
            fn=update_patient_profile,
            inputs=[case_patient_select, edit_patient_name, edit_patient_reference, storage_dir],
            outputs=[
                patient_select,
                case_patient_select,
                history_patient_select,
                edit_patient_name,
                edit_patient_reference,
                archive_patient_btn,
                patient_feedback,
            ],
        )
        archive_patient_btn.click(
            fn=archive_patient_profile,
            inputs=[case_patient_select, storage_dir],
            outputs=[
                patient_select,
                case_patient_select,
                history_patient_select,
                archived_patient_select,
                edit_patient_name,
                edit_patient_reference,
                archive_patient_btn,
                restore_patient_btn,
                patient_feedback,
            ],
        ).then(
            fn=clear_patient_session,
            outputs=[image, batch_files, *common_outputs, case_id, case_note],
        ).then(
            fn=refresh_case_records,
            inputs=[storage_dir, case_patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, case_patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, case_patient_select],
            outputs=report_list_outputs,
        )
        restore_patient_btn.click(
            fn=restore_patient_profile,
            inputs=[archived_patient_select, storage_dir],
            outputs=[
                patient_select,
                case_patient_select,
                history_patient_select,
                archived_patient_select,
                edit_patient_name,
                edit_patient_reference,
                archive_patient_btn,
                restore_patient_btn,
                patient_feedback,
            ],
        ).then(
            fn=clear_patient_session,
            outputs=[image, batch_files, *common_outputs, case_id, case_note],
        ).then(
            fn=refresh_case_records,
            inputs=[storage_dir, case_patient_select],
            outputs=case_list_outputs,
        ).then(
            fn=refresh_history_records,
            inputs=[storage_dir, case_patient_select],
            outputs=history_list_outputs,
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, case_patient_select],
            outputs=report_list_outputs,
        )
        # User-only listeners avoid reprocessing when another callback updates a component.
        # This is important for large images and model outputs: Gradio's `.change()` also
        # fires for function updates, which can create duplicate redraws or event loops.
        image.input(fn=clear_outputs_with_quality, inputs=image, outputs=common_outputs)
        batch_files.upload(fn=clear_outputs, outputs=common_outputs)
        batch_files.clear(fn=clear_outputs, outputs=common_outputs)
        stale_result_controls = [primary_model_path, compare_model_path, conf, iou, device_choice, use_clahe]
        for control in stale_result_controls:
            control.input(fn=clear_outputs_with_quality, inputs=image, outputs=common_outputs)
        primary_model_path.input(fn=_workbench_model_status_html, inputs=primary_model_path, outputs=workbench_model_status)
        example_select.input(fn=_example_preview_text, inputs=example_select, outputs=example_info)
        load_example_btn.click(fn=load_demo_example, inputs=example_select, outputs=[image, example_info]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        run_btn.click(
            fn=run_single_detection,
            inputs=[image, *common_inputs],
            outputs=common_outputs,
            concurrency_limit=1,
            concurrency_id=INFERENCE_CONCURRENCY_ID,
            show_progress="minimal",
        )
        batch_btn.click(
            fn=run_batch_detection,
            inputs=[batch_files, *common_inputs],
            outputs=common_outputs,
            concurrency_limit=1,
            concurrency_id=INFERENCE_CONCURRENCY_ID,
            show_progress="minimal",
        )
        batch_select.input(
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
        visible_class_filter.input(
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
        ai_enabled.input(fn=toggle_ai_settings, inputs=ai_enabled, outputs=ai_group)
        key_mode.input(
            fn=set_api_key_mode,
            inputs=key_mode,
            outputs=[env_api_key, direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        )
        show_direct_key_btn.click(
            fn=toggle_direct_key_visibility,
            inputs=[direct_api_key_hidden, direct_api_key_visible, direct_key_visible],
            outputs=[direct_api_key_hidden, direct_api_key_visible, show_direct_key_btn, direct_key_visible],
        )
        model_mode.input(fn=sync_model_mode, inputs=model_mode, outputs=[settings_model_mode, compare_model_path]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        settings_model_mode.input(fn=sync_model_mode, inputs=settings_model_mode, outputs=[model_mode, compare_model_path]).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        enable_compare.input(
            fn=on_enable_compare_change,
            inputs=enable_compare,
            outputs=[model_mode, settings_model_mode, compare_model_path],
        ).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        show_summary.input(fn=toggle_summary, inputs=show_summary, outputs=summary)
        test_btn.click(
            fn=test_ai_settings,
            inputs=settings.ai_request_inputs(),
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
                patient_select,
                case_patient_select,
                history_patient_select,
                archived_patient_select,
                edit_patient_name,
                edit_patient_reference,
                archive_patient_btn,
                restore_patient_btn,
                case_loaded_state,
                history_loaded_state,
                storage_changed_state,
            ],
        ).then(
            fn=refresh_report_center_after_storage_change,
            inputs=[storage_changed_state, storage_dir, history_patient_select],
            outputs=report_list_outputs,
        )
        chat_btn.click(
            fn=continue_chat,
            inputs=[chat_input, chat_state, *settings.ai_request_inputs()],
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        chat_input.submit(
            fn=continue_chat,
            inputs=[chat_input, chat_state, *settings.ai_request_inputs()],
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        clear_chat_btn.click(
            fn=clear_current_chat,
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        refresh_model_btn.click(
            fn=refresh_model_choices,
            inputs=[model_dir, model_file_select, show_advanced_models],
            outputs=[model_file_select, model_feedback],
        )
        show_advanced_models.input(
            fn=refresh_model_choices,
            inputs=[model_dir, model_file_select, show_advanced_models],
            outputs=[model_file_select, model_feedback],
        )
        open_model_dir_btn.click(
            fn=choose_model_dir,
            inputs=[model_dir, model_file_select, show_advanced_models],
            outputs=[model_dir, model_file_select, model_feedback],
        )
        apply_model_btn.click(
            fn=apply_selected_model,
            inputs=[model_file_select, model_apply_target],
            outputs=[primary_model_path, compare_model_path, model_cards_view, model_info_markdown, model_feedback],
        ).then(
            fn=_workbench_model_status_html,
            inputs=primary_model_path,
            outputs=workbench_model_status,
        ).then(
            fn=clear_outputs_with_quality,
            inputs=image,
            outputs=common_outputs,
        )
        apply_model_card_btn.click(
            fn=apply_model_card,
            inputs=[model_card_select, model_dir, show_advanced_models],
            outputs=[primary_model_path, model_file_select, model_cards_view, model_info_markdown, model_feedback],
        ).then(
            fn=_workbench_model_status_html,
            inputs=primary_model_path,
            outputs=workbench_model_status,
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
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, history_patient_select],
            outputs=report_list_outputs,
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
        ).then(
            fn=refresh_report_center,
            inputs=[storage_dir, history_patient_select],
            outputs=report_list_outputs,
        )
        save_case_btn.click(
            fn=save_case_record,
            inputs=[batch_state, batch_select, case_id, case_note, storage_dir],
            outputs=[case_feedback, case_select, case_table, case_detail, case_report_file, case_report_path],
        )
        refresh_case_btn.click(
            fn=refresh_case_records,
            inputs=[storage_dir, case_patient_select],
            outputs=case_list_outputs,
        )
        search_case_btn.click(
            fn=search_case_records_ui,
            inputs=[
                case_keyword,
                case_class_filter,
                case_level_filter,
                case_date_from,
                case_date_to,
                storage_dir,
                case_patient_select,
            ],
            outputs=case_list_outputs,
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
                case_patient_select,
            ],
            outputs=[case_select, case_table, case_feedback, case_detail, case_report_file, case_report_path],
        )
        export_case_btn.click(
            fn=export_selected_case_record,
            inputs=[case_select, storage_dir, case_patient_select],
            outputs=[case_report_file, case_report_path],
        )
        case_select.input(
            fn=load_case_record_and_clear_export,
            inputs=[case_select, storage_dir, case_patient_select],
            outputs=[case_detail, case_report_file, case_report_path],
        )
        refresh_history_btn.click(
            fn=refresh_history_records,
            inputs=[storage_dir, history_patient_select],
            outputs=history_list_outputs,
        )
        history_select.input(
            fn=load_history_record,
            inputs=[history_select, storage_dir, history_patient_select],
            outputs=history_detail,
        )
        delete_history_btn.click(
            fn=delete_selected_history_record,
            inputs=[history_select, storage_dir, history_patient_select],
            outputs=history_list_outputs,
        )
        clear_history_btn.click(
            fn=clear_all_history_records,
            inputs=[storage_dir, history_patient_select],
            outputs=history_list_outputs,
        )
        report_center.refresh_button.click(
            fn=refresh_report_center,
            inputs=[storage_dir, history_patient_select],
            outputs=report_list_outputs,
        )
        report_center.report_select.input(
            fn=load_report_center_item,
            inputs=[report_center.report_select, storage_dir, history_patient_select],
            outputs=[
                report_center.report_detail,
                report_center.report_file,
                report_center.report_feedback,
                report_center.trash_button,
            ],
        )
        report_center.trash_button.click(
            fn=trash_report_center_item,
            inputs=[report_center.report_select, storage_dir, history_patient_select],
            outputs=report_list_outputs,
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
        css=load_workbench_css(),
        js=load_workbench_js(),
        allowed_paths=[str(root) for root in _allowed_file_roots()],
    )
