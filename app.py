from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Any
import zipfile

import gradio as gr
import pandas as pd
import torch
from PIL import ImageOps, ImageStat

from src.dental_detection.assistant import (
    APP_HOME,
    AiSettings,
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
from src.dental_detection.config import DEFAULT_MODEL_NAME, MODEL_REGISTRY, PROJECT_ROOT
from src.dental_detection.inference import Detection, run_inference

MODEL_SOURCE = "YOLOv8m 原始结构"
MODEL_OPTIMIZED = "YOLOv8m C2f-Faster-lite"
MODEL_COMPARE = "双模型对比"
TABLE_COLUMNS = ["class", "confidence", "x1", "y1", "x2", "y2"]
CSS_PATH = PROJECT_ROOT / "assets" / "workbench.css"
STARTUP_STORAGE_ROOT = Path(load_settings().storage_dir).expanduser()


def _load_workbench_css() -> str:
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return ""


def _allowed_file_roots() -> list[Path]:
    roots = [Path.home(), PROJECT_ROOT.parent, APP_HOME, STARTUP_STORAGE_ROOT]
    resolved: list[Path] = []
    for root in roots:
        if root.exists():
            path = root.resolve()
            if path not in resolved:
                resolved.append(path)
    return resolved


def _is_within_known_download_roots(path: str | Path) -> bool:
    target = Path(path).expanduser().resolve()
    return any(target == root or root in target.parents for root in _allowed_file_roots())


def _can_return_file(path: str | Path) -> bool:
    target = Path(path).expanduser().resolve()
    return any(target == root or root in target.parents for root in _allowed_file_roots())


def _file_output(path: str | Path) -> str | None:
    return str(path) if _can_return_file(path) else None


def _file_component_output(path: str | Path):
    file_path = _file_output(path)
    return gr.update(value=file_path, visible=bool(file_path))


def _clear_file_output():
    return gr.update(value=None, visible=False)


def _empty_table() -> pd.DataFrame:
    return pd.DataFrame(columns=TABLE_COLUMNS)


def _table_from_detections(detections: list[Detection]) -> pd.DataFrame:
    rows = [det.as_row() for det in detections]
    return pd.DataFrame(rows, columns=TABLE_COLUMNS) if rows else _empty_table()


def _records_from_detections(detections: list[Detection]) -> list[dict[str, Any]]:
    return [det.as_row() for det in detections]


def assess_image_quality(image) -> str:
    if image is None:
        return "尚未上传图片。"
    pil_image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = pil_image.size
    gray = pil_image.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    ratio = max(width, height) / max(1, min(width, height))

    notes = [
        f"图像尺寸：{width} x {height}",
        f"平均亮度：{brightness:.1f}",
        f"对比度估计：{contrast:.1f}",
    ]
    warnings = []
    if min(width, height) < 512:
        warnings.append("分辨率偏低，细小病变区域可能不稳定。")
    if brightness < 45:
        warnings.append("图像整体偏暗，建议确认牙片曝光或阅片窗宽窗位。")
    elif brightness > 220:
        warnings.append("图像整体偏亮，建议确认牙片曝光或显示设置。")
    if contrast < 28:
        warnings.append("对比度偏低，可尝试勾选 CLAHE 增强后推理进行辅助对照。")
    if ratio > 4:
        warnings.append("宽高比非常极端，建议确认是否上传了完整牙片而不是过窄裁剪。")

    if warnings:
        return "\n".join(["图像质量提示：", *notes, *[f"- {item}" for item in warnings]])
    return "\n".join(["图像质量提示：当前未发现明显输入质量风险。", *notes])


def _device(use_gpu: bool) -> tuple[str | int, bool]:
    cuda_available = torch.cuda.is_available()
    if use_gpu and not cuda_available:
        raise gr.Error("当前 Python 环境没有可用 CUDA。请使用 mamba 的 yolo 环境启动应用。")
    return (0 if use_gpu and cuda_available else "cpu"), cuda_available


def _detect_model(model_name: str, image, use_clahe: bool, conf: float, iou: float, device):
    model_info = MODEL_REGISTRY[model_name]
    original, model_input, annotated, detections, names = run_inference(
        image=image,
        model_path=model_info["path"],
        use_clahe=use_clahe,
        conf=conf,
        iou=iou,
        imgsz=1280,
        device=device,
    )
    return {
        "model": model_name,
        "original": original,
        "model_input": model_input,
        "annotated": annotated,
        "detections": _records_from_detections(detections),
        "table": _table_from_detections(detections),
        "class_names": {str(key): value for key, value in names.items()},
    }


def _ai_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
) -> AiSettings:
    return AiSettings(
        enabled=ai_enabled,
        base_url=normalize_base_url(base_url),
        model=(ai_model or "").strip() or DEFAULT_AI_MODEL,
        key_mode=key_mode,
        api_key=(api_key or "").strip(),
        save_api_key=save_key,
        auto_save=auto_save,
        storage_dir=(storage_dir or "").strip() or str(ensure_app_dirs()),
        custom_prompt=(custom_prompt or "").strip() or DEFAULT_AI_PROMPT,
    )


def _build_advice(settings: AiSettings, detections: list[dict[str, Any]]) -> str:
    if not settings.enabled:
        return default_advice(detections)
    try:
        return chat_completion(
            settings,
            detection_prompt(detections, settings.custom_prompt),
            temperature=0.2,
            max_tokens=500,
        )
    except Exception as exc:
        return f"{default_advice(detections)}\n\nAI 建议生成失败：{exc}"


def _conversation_from_advice(advice: str) -> list[dict[str, str]]:
    return [{"role": "assistant", "content": advice}]


def _suggestion_type(ai_enabled: bool) -> str:
    return "ai" if ai_enabled else "default"


def _safe_stem(name: str) -> str:
    stem = Path(name).stem or "image"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "image"


def _current_item(batch_state: list[dict[str, Any]], selected_name: str | None = None) -> dict[str, Any]:
    if not batch_state:
        raise gr.Error("当前没有可用的检测结果。")
    if selected_name:
        for item in batch_state:
            if item.get("display_name") == selected_name or item.get("name") == selected_name:
                return item
    return batch_state[0]


def _case_choices(storage_dir: str) -> list[str]:
    ensure_app_dirs(storage_dir)
    choices = []
    for path in sorted(case_dir(storage_dir).glob("case_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        title = data.get("case_id") or path.stem
        image_name = data.get("image_name") or "未命名图片"
        created_at = data.get("created_at") or ""
        choices.append(f"{created_at} | {title} | {image_name} | {path.name}")
    return choices


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _detections_html(detections: list[dict[str, Any]]) -> str:
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


def _unique_report_paths(storage_dir: str, stamp: str) -> tuple[Path, Path]:
    base = report_dir(storage_dir)
    root = base / f"single_report_{stamp}"
    counter = 1
    while root.exists():
        root = base / f"single_report_{stamp}_{counter:02d}"
        counter += 1
    return root, root / f"{root.name}.zip"


def _summary_lines(batch_state: list[dict[str, Any]], export_info: dict[str, Any]) -> list[str]:
    class_counts: Counter[str] = Counter()
    total_boxes = 0
    for item in batch_state:
        result = item.get("result") or item
        detections = result.get("detections", [])
        total_boxes += len(detections)
        class_counts.update(str(det.get("class", "unknown")) for det in detections)

    lines = [
        "YOLO Dental Lesion Detection Batch Export",
        f"导出时间: {export_info['exported_at']}",
        f"图片数量: {len(batch_state)}",
        f"检测到的总框数: {total_boxes}",
        f"是否使用 CLAHE: {export_info['use_clahe']}",
        f"conf: {export_info['conf']}",
        f"iou: {export_info['iou']}",
        f"model: {export_info['model']}",
        "",
        "各类别数量:",
    ]
    if class_counts:
        lines.extend(f"- {name}: {count}" for name, count in sorted(class_counts.items()))
    else:
        lines.append("- 无检测框")
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


def export_batch_results(batch_state: list[dict[str, Any]], storage_dir: str):
    if not batch_state:
        raise gr.Error("请先完成批量检测，再导出结果。")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ensure_app_dirs(storage_dir)
    export_root, zip_path = _unique_batch_export_paths(storage_dir, stamp)
    export_root.mkdir(parents=True, exist_ok=True)
    work_dir = export_root / "payload"
    images_dir = work_dir / "images"
    suggestions_dir = work_dir / "suggestions"
    images_dir.mkdir(parents=True, exist_ok=True)
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    first_summary = batch_state[0].get("summary", {})
    export_info = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "image_count": len(batch_state),
        "use_clahe": bool(first_summary.get("CLAHE增强", False)),
        "conf": first_summary.get("conf", "unknown"),
        "iou": first_summary.get("iou", "unknown"),
        "model": first_summary.get("模型", "unknown"),
    }
    try:
        csv_rows: list[dict[str, Any]] = []
        json_items = []

        for index, item in enumerate(batch_state, start=1):
            name = item.get("name") or item.get("image_name") or f"image_{index:03d}.png"
            stem = f"{index:03d}_{_safe_stem(name)}"
            result = item.get("result") or item
            suggestion_type = item.get("suggestion_type", "default")
            advice = item.get("advice") or item.get("suggestion") or ""

            original_image = result.get("original") or result.get("original_image")
            input_image = result.get("model_input") or result.get("input_image")
            annotated_image = result.get("annotated") or result.get("result_image")
            if original_image is None or input_image is None or annotated_image is None:
                raise gr.Error(f"{name} 的批量结果不完整，无法导出图片。")

            original_image.save(images_dir / f"{stem}_original.png")
            input_image.save(images_dir / f"{stem}_input.png")
            annotated_image.save(images_dir / f"{stem}_result.png")
            (suggestions_dir / f"{stem}.txt").write_text(advice, encoding="utf-8")

            detections = result.get("detections", [])
            if detections:
                for det in detections:
                    csv_rows.append(
                        {
                            "image_name": name,
                            "class": det.get("class", ""),
                            "confidence": det.get("confidence", ""),
                            "x1": det.get("x1", ""),
                            "y1": det.get("y1", ""),
                            "x2": det.get("x2", ""),
                            "y2": det.get("y2", ""),
                            "suggestion_type": suggestion_type,
                        }
                    )
            else:
                csv_rows.append(
                    {
                        "image_name": name,
                        "class": "",
                        "confidence": "",
                        "x1": "",
                        "y1": "",
                        "x2": "",
                        "y2": "",
                        "suggestion_type": suggestion_type,
                    }
                )

            json_items.append(
                {
                    "image_name": name,
                    "model": result.get("model", item.get("model", "unknown")),
                    "suggestion_type": suggestion_type,
                    "suggestion": advice,
                    "detections": detections,
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
                fieldnames=["image_name", "class", "confidence", "x1", "y1", "x2", "y2", "suggestion_type"],
            )
            writer.writeheader()
            writer.writerows(csv_rows)

        (work_dir / "detections.json").write_text(
            json.dumps({"export": export_info, "items": json_items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (work_dir / "summary.txt").write_text(
            "\n".join(_summary_lines(batch_state, export_info)) + "\n",
            encoding="utf-8",
        )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in work_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(work_dir).as_posix())
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)
        if not zip_path.exists() and export_root.exists() and not any(export_root.iterdir()):
            export_root.rmdir()
    return _file_component_output(zip_path), f"已导出：{zip_path}"


def export_single_report(batch_state: list[dict[str, Any]], selected_name: str, storage_dir: str):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ensure_app_dirs(storage_dir)
    report_root, zip_path = _unique_report_paths(storage_dir, stamp)
    report_root.mkdir(parents=True, exist_ok=True)
    work_dir = report_root / "payload"
    images_dir = work_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    name = item.get("name") or item.get("image_name") or "当前单图"
    stem = _safe_stem(name)
    advice = item.get("advice") or ""
    detections = result.get("detections", [])
    summary_data = item.get("summary", {})
    export_info = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "image_name": name,
        "model": result.get("model", summary_data.get("模型", "unknown")),
        "suggestion_type": item.get("suggestion_type", "default"),
        "safety_notice": SAFETY_NOTICE,
    }
    try:
        image_files = {
            "original": f"images/{stem}_original.png",
            "input": f"images/{stem}_input.png",
            "result": f"images/{stem}_result.png",
        }
        result["original"].save(work_dir / image_files["original"])
        result["model_input"].save(work_dir / image_files["input"])
        result["annotated"].save(work_dir / image_files["result"])

        csv_path = work_dir / "detections.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_COLUMNS)
            writer.writeheader()
            writer.writerows(detections)

        _write_text(
            work_dir / "detections.json",
            json.dumps(
                {
                    "report": export_info,
                    "summary": summary_data,
                    "detections": detections,
                    "image_files": image_files,
                },
                ensure_ascii=False,
                indent=2,
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
                    f"模型: {export_info['model']}",
                    f"建议类型: {export_info['suggestion_type']}",
                    f"检测框数量: {len(detections)}",
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
  </style>
</head>
<body>
  <h1>牙齿病变辅助检测报告</h1>
  <p class="notice">{_html_escape(SAFETY_NOTICE)}</p>
  <p>生成时间：{_html_escape(export_info['created_at'])}</p>
  <p>图片名称：{_html_escape(name)}；模型：{_html_escape(export_info['model'])}</p>
  <div class="grid">
    <figure><img src="{image_files['original']}"><figcaption>原始上传图</figcaption></figure>
    <figure><img src="{image_files['input']}"><figcaption>实际送入模型的图</figcaption></figure>
    <figure><img src="{image_files['result']}"><figcaption>检测结果图</figcaption></figure>
  </div>
  <h2>检测框</h2>
  {_detections_html(detections)}
  <h2>辅助建议</h2>
  <pre>{_html_escape(advice)}</pre>
  <h2>参数摘要</h2>
  <pre>{_html_escape(json.dumps(summary_data, ensure_ascii=False, indent=2))}</pre>
</body>
</html>
"""
        _write_text(work_dir / "report.html", html)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in work_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(work_dir).as_posix())
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)
        if not zip_path.exists() and report_root.exists() and not any(report_root.iterdir()):
            report_root.rmdir()
    return _file_component_output(zip_path), f"已导出单图报告：{zip_path}"


def save_case_record(
    batch_state: list[dict[str, Any]],
    selected_name: str,
    case_id: str,
    case_note: str,
    storage_dir: str,
):
    item = _current_item(batch_state, selected_name)
    result = item.get("result") or item
    ensure_app_dirs(storage_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_case = _safe_stem(case_id or item.get("name") or "case")
    path = case_dir(storage_dir) / f"case_{stamp}_{safe_case}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "case_id": case_id.strip() if case_id else "未填写",
        "note": case_note.strip() if case_note else "",
        "image_name": item.get("name") or "当前单图",
        "summary": item.get("summary", {}),
        "detections": result.get("detections", []),
        "suggestion_type": item.get("suggestion_type", "default"),
        "suggestion": item.get("advice", ""),
        "safety_notice": SAFETY_NOTICE,
    }
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    choices = _case_choices(storage_dir)
    selected = next((choice for choice in choices if path.name in choice), choices[0] if choices else None)
    return f"病例记录已保存：{path}", gr.update(choices=choices, value=selected), payload


def refresh_case_records(storage_dir: str):
    choices = _case_choices(storage_dir)
    return gr.update(choices=choices, value=choices[0] if choices else None), (
        "已刷新病例记录。" if choices else "暂无病例记录。"
    )


def load_case_record(choice: str, storage_dir: str):
    if not choice:
        return {}
    file_name = choice.split("|")[-1].strip()
    path = case_dir(storage_dir) / file_name
    if not path.exists():
        return {"错误": f"病例文件不存在：{path}"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"错误": str(exc)}


def clear_outputs():
    return (
        None,
        None,
        None,
        _empty_table(),
        "",
        "尚未上传图片。",
        {},
        [],
        gr.update(choices=[], value=None),
        [],
        [],
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        gr.update(interactive=False),
    )


def clear_outputs_with_quality(image):
    values = list(clear_outputs())
    values[5] = assess_image_quality(image)
    return tuple(values)


def run_single_detection(
    image,
    model_choice: str,
    conf: float,
    iou: float,
    use_gpu: bool,
    use_clahe: bool,
    enable_compare: bool,
    show_summary: bool,
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
):
    if image is None:
        raise gr.Error("请先上传一张牙科影像。")

    device, cuda_available = _device(use_gpu)
    selected_models = [model_choice]
    if enable_compare and model_choice == MODEL_COMPARE:
        selected_models = [MODEL_SOURCE, MODEL_OPTIMIZED]
    elif model_choice == MODEL_COMPARE:
        selected_models = [MODEL_OPTIMIZED]

    primary = None
    all_results = []
    for model_name in selected_models:
        result = _detect_model(model_name, image, use_clahe, conf, iou, device)
        all_results.append(result)
        if primary is None:
            primary = result

    assert primary is not None
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        api_key,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
    )
    save_settings(settings)
    advice = _build_advice(settings, primary["detections"])
    chat_history = _conversation_from_advice(advice)
    if settings.auto_save:
        save_conversation(chat_history, settings.storage_dir)

    summary = {
        "运行设备": "cuda:0" if device != "cpu" else "cpu",
        "GPU请求": bool(use_gpu),
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
                "路径": str(MODEL_REGISTRY[item["model"]]["path"]),
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
            "summary": summary,
        }
    ]
    return (
        primary["original"],
        primary["model_input"],
        primary["annotated"],
        primary["table"],
        advice,
        assess_image_quality(primary["original"]),
        gr.update(value=summary, visible=show_summary),
        batch_state,
        gr.update(choices=["当前单图"], value="当前单图"),
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        gr.update(interactive=False),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        gr.update(interactive=True),
    )


def _file_name(file_obj) -> str:
    path = getattr(file_obj, "name", None) or str(file_obj)
    return Path(path).name


def run_batch_detection(
    files,
    model_choice: str,
    conf: float,
    iou: float,
    use_gpu: bool,
    use_clahe: bool,
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
):
    if not files:
        raise gr.Error("请先批量上传牙科影像。")

    device, _ = _device(use_gpu)
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        api_key,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
    )
    save_settings(settings)
    selected_model = MODEL_OPTIMIZED if model_choice == MODEL_COMPARE else model_choice
    batch_state = []
    for index, file_obj in enumerate(files, start=1):
        path = getattr(file_obj, "name", None) or file_obj
        file_name = _file_name(file_obj)
        result = _detect_model(selected_model, path, use_clahe, conf, iou, device)
        advice = _build_advice(settings, result["detections"])
        batch_state.append(
            {
                "name": file_name,
                "display_name": f"{index:03d} - {file_name}",
                "result": result,
                "all_results": [result],
                "advice": advice,
                "suggestion_type": _suggestion_type(settings.enabled),
                "summary": {
                    "文件": file_name,
                    "模型": selected_model,
                    "检测数量": len(result["detections"]),
                    "CLAHE增强": bool(use_clahe),
                    "conf": conf,
                    "iou": iou,
                },
            }
        )

    first = batch_state[0]
    chat_history = _conversation_from_advice(first["advice"])
    if settings.auto_save:
        save_conversation(chat_history, settings.storage_dir)
    choices = [item["display_name"] for item in batch_state]
    return (
        first["result"]["original"],
        first["result"]["model_input"],
        first["result"]["annotated"],
        first["result"]["table"],
        first["advice"],
        assess_image_quality(first["result"]["original"]),
        first["summary"],
        batch_state,
        gr.update(choices=choices, value=choices[0]),
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        gr.update(interactive=True),
    )


def select_batch_item(name: str, batch_state: list[dict[str, Any]]):
    if not name or not batch_state:
        return (
            None,
            None,
            None,
            _empty_table(),
            "",
            "尚未上传图片。",
            {},
            [],
            [],
            _clear_file_output(),
            "",
            _clear_file_output(),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )
    item = next(
        (row for row in batch_state if row.get("display_name") == name or row.get("name") == name),
        batch_state[0],
    )
    chat_history = _conversation_from_advice(item["advice"])
    return (
        item["result"]["original"],
        item["result"]["model_input"],
        item["result"]["annotated"],
        item["result"]["table"],
        item["advice"],
        assess_image_quality(item["result"]["original"]),
        item["summary"],
        chat_history,
        chat_history,
        _clear_file_output(),
        "",
        _clear_file_output(),
        "",
        gr.update(interactive=True),
        gr.update(interactive=True),
    )


def test_ai_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
):
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        api_key,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
    )
    save_settings(settings)
    if not settings.enabled:
        return "AI 功能未开启。开启后可测试接口。"
    try:
        return test_chat_completion(settings)
    except Exception as exc:
        return f"测试失败：{exc}"


def save_ui_settings(
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
):
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        api_key,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
    )
    path = save_settings(settings)
    feedback = [f"设置已保存：{path}"]
    if not _is_within_known_download_roots(settings.storage_dir):
        feedback.append(
            "提示：新的存储位置不在当前 Gradio 文件下载白名单内。"
            "设置已生效，但如需直接下载该目录下的报告或导出文件，请重启项目脚本。"
        )
    case_choices = _case_choices(settings.storage_dir)
    case_message = "病例列表已同步到当前存储位置。" if case_choices else "当前存储位置暂无病例记录。"
    return (
        "\n".join(feedback),
        gr.update(choices=case_choices, value=case_choices[0] if case_choices else None),
        case_message,
    )


def continue_chat(
    message: str,
    history: list[dict[str, str]],
    ai_enabled: bool,
    base_url: str,
    ai_model: str,
    key_mode: str,
    api_key: str,
    save_key: bool,
    auto_save: bool,
    storage_dir: str,
    custom_prompt: str,
):
    if not message:
        return history, history, "", _clear_file_output(), ""
    settings = _ai_settings(
        ai_enabled,
        base_url,
        ai_model,
        key_mode,
        api_key,
        save_key,
        auto_save,
        storage_dir,
        custom_prompt,
    )
    history = list(history or [])
    history.append({"role": "user", "content": message})
    if not settings.enabled:
        history.append(
            {
                "role": "assistant",
                "content": "AI 功能未开启。当前只能查看检测后的内置建议。",
            }
        )
    else:
        try:
            messages = [{"role": "system", "content": settings.custom_prompt}, *history]
            answer = chat_completion(settings, messages, temperature=0.2, max_tokens=500)
        except Exception as exc:
            answer = f"AI 回复失败：{exc}"
        history.append({"role": "assistant", "content": answer})
    if settings.auto_save:
        save_conversation(history, settings.storage_dir)
    return history, history, "", _clear_file_output(), ""


def export_chat(history: list[dict[str, str]], storage_dir: str):
    if not history:
        raise gr.Error("当前没有可导出的对话记录。")
    path = save_conversation(history, storage_dir)
    return _file_component_output(path), f"已导出：{path}"


def toggle_ai_settings(enabled: bool):
    return gr.update(visible=enabled)


def toggle_summary(show_summary: bool):
    return gr.update(visible=show_summary)


def toggle_compare_options(enabled: bool, current_model: str):
    choices = [MODEL_OPTIMIZED, MODEL_SOURCE]
    if enabled:
        choices.append(MODEL_COMPARE)
    value = current_model if current_model in choices else MODEL_OPTIMIZED
    return gr.update(choices=choices, value=value)


def _with_current_defaults(saved: AiSettings) -> AiSettings:
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
    saved = _with_current_defaults(load_settings())
    ensure_app_dirs(saved.storage_dir)
    with gr.Blocks(title="牙齿病变区域识别") as demo:
        batch_state = gr.State([])
        chat_state = gr.State([])
        gr.HTML(f"<style>{_load_workbench_css()}</style>")
        gr.Markdown(
            "医院与个人辅助筛查工作台\n"
            "# 牙齿病变区域识别\n"
            "上传牙科影像，查看模型输入、检测框和辅助建议。结果仅供参考，不能替代专业牙科医生诊断。"
        )

        with gr.Tabs():
            with gr.Tab("检测工作台"):
                with gr.Row():
                    with gr.Column(scale=4):
                        with gr.Tabs():
                            with gr.Tab("单张分析"):
                                image = gr.Image(
                                    type="pil",
                                    label="拖拽或点击上传牙科影像",
                                    height=390,
                                    sources=["upload", "clipboard"],
                                )
                                run_btn = gr.Button("开始分析", variant="primary")
                            with gr.Tab("批量分析"):
                                batch_files = gr.File(
                                    label="批量上传图片",
                                    file_count="multiple",
                                    file_types=["image"],
                                )
                                batch_btn = gr.Button("批量分析", variant="primary")
                                batch_select = gr.Dropdown(label="查看某张图片", choices=[])
                                export_batch_btn = gr.Button("一键导出批量结果", interactive=False)
                                batch_export_file = gr.File(label="批量结果 ZIP", visible=False)
                                batch_export_path = gr.Textbox(label="导出路径", interactive=False)

                        with gr.Row():
                            model_choice = gr.Radio(
                                choices=[MODEL_OPTIMIZED, MODEL_SOURCE, MODEL_COMPARE],
                                value=DEFAULT_MODEL_NAME,
                                label="模型",
                            )
                            use_gpu = gr.Checkbox(value=torch.cuda.is_available(), label="GPU")
                        with gr.Row():
                            conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度")
                            iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU")
                        use_clahe = gr.Checkbox(
                            value=False,
                            label="使用 CLAHE 增强后推理（适合低对比度牙片）",
                        )

                    with gr.Column(scale=7):
                        with gr.Row():
                            original_output = gr.Image(type="pil", label="原始上传图", height=260)
                            model_input_output = gr.Image(type="pil", label="实际送入模型的图", height=260)
                            result_output = gr.Image(type="pil", label="检测结果图", height=260)
                        det_table = gr.Dataframe(
                            headers=TABLE_COLUMNS,
                            label="检测框表格",
                            wrap=True,
                            interactive=False,
                        )
                        advice_box = gr.Textbox(label="牙齿辅助建议", lines=7, interactive=False)
                        quality_box = gr.Textbox(
                            value="尚未上传图片。",
                            label="图像质量提示",
                            lines=5,
                            interactive=False,
                        )
                        summary = gr.JSON(label="参数与检测摘要", visible=False)
                        with gr.Row():
                            export_report_btn = gr.Button("导出当前单图报告", interactive=False)
                            report_file = gr.File(label="单图报告 ZIP", visible=False)
                        report_path = gr.Textbox(label="报告路径", interactive=False)

            with gr.Tab("AI 问答"):
                chatbot = gr.Chatbot(label="问答记录", height=360)
                with gr.Row():
                    chat_input = gr.Textbox(label="继续提问", scale=6)
                    chat_btn = gr.Button("发送", variant="primary", scale=1)
                with gr.Row():
                    export_btn = gr.Button("导出当前对话")
                    export_file = gr.File(label="导出的对话文件", visible=False)
                export_path = gr.Textbox(label="导出路径", interactive=False)

            with gr.Tab("病例记录"):
                gr.Markdown(
                    "保存当前检测摘要、检测框和建议，便于后续复查。不会自动保存原始牙片图片。"
                )
                with gr.Row():
                    case_id = gr.Textbox(label="病例编号 / 备注名称", placeholder="例如：20260602-复查")
                    case_note = gr.Textbox(label="病例备注", placeholder="可填写主诉、复查说明或医生备注")
                with gr.Row():
                    save_case_btn = gr.Button(
                        "保存当前结果为病例记录",
                        variant="primary",
                        interactive=False,
                    )
                    refresh_case_btn = gr.Button("刷新病例记录")
                case_feedback = gr.Textbox(label="病例反馈", interactive=False)
                case_select = gr.Dropdown(label="已保存病例", choices=_case_choices(saved.storage_dir))
                case_detail = gr.JSON(label="病例详情")

            with gr.Tab("设置"):
                with gr.Tabs():
                    with gr.Tab("检测显示"):
                        enable_compare = gr.Checkbox(value=True, label="启用双模型对比选项")
                        show_summary = gr.Checkbox(value=False, label="显示参数分析和摘要")
                    with gr.Tab("AI 建议"):
                        ai_enabled = gr.Checkbox(value=saved.enabled, label="启用 AI 建议与问答")
                        with gr.Group(visible=saved.enabled) as ai_group:
                            ai_model = gr.Textbox(value=saved.model, label="模型")
                            base_url = gr.Textbox(value=saved.base_url, label="接口 API / base_url")
                            key_mode = gr.Radio(
                                choices=["环境变量", "直接 Key 值"],
                                value=saved.key_mode,
                                label="API Key 类型",
                            )
                            api_key = gr.Textbox(
                                value=saved.api_key if saved.save_api_key or saved.key_mode == "环境变量" else "",
                                label="API Key 或环境变量名",
                                type="password",
                            )
                            save_key = gr.Checkbox(value=saved.save_api_key, label="保存 API Key 到本地配置")
                            custom_prompt = gr.Textbox(
                                value=saved.custom_prompt or DEFAULT_AI_PROMPT,
                                label="AI 建议 Prompt",
                                lines=7,
                            )
                            test_btn = gr.Button("测试接口")
                            test_result = gr.Textbox(label="测试反馈", interactive=False)
                    with gr.Tab("对话记录"):
                        auto_save = gr.Checkbox(value=saved.auto_save, label="自动保存对话记录")
                        storage_dir = gr.Textbox(value=saved.storage_dir, label="存储位置（数据根目录）")
                    with gr.Tab("高级接口"):
                        gr.Markdown(
                            "第一版固定使用 OpenAI-compatible Chat Completions `/v1/chat/completions`。"
                            "请求字段只使用 `model`、`messages`、`temperature`、`max_tokens`。"
                        )
                save_settings_btn = gr.Button("保存设置", variant="primary")
                settings_feedback = gr.Textbox(label="设置反馈", interactive=False)

        common_inputs = [
            model_choice,
            conf,
            iou,
            use_gpu,
            use_clahe,
            enable_compare,
            show_summary,
            ai_enabled,
            base_url,
            ai_model,
            key_mode,
            api_key,
            save_key,
            auto_save,
            storage_dir,
            custom_prompt,
        ]
        common_outputs = [
            original_output,
            model_input_output,
            result_output,
            det_table,
            advice_box,
            quality_box,
            summary,
            batch_state,
            batch_select,
            chatbot,
            chat_state,
            batch_export_file,
            batch_export_path,
            export_batch_btn,
            export_file,
            export_path,
            report_file,
            report_path,
            export_report_btn,
            save_case_btn,
        ]

        image.change(fn=clear_outputs_with_quality, inputs=image, outputs=common_outputs)
        batch_files.change(fn=clear_outputs, outputs=common_outputs)
        run_btn.click(fn=run_single_detection, inputs=[image, *common_inputs], outputs=common_outputs)
        batch_btn.click(
            fn=run_batch_detection,
            inputs=[
                batch_files,
                model_choice,
                conf,
                iou,
                use_gpu,
                use_clahe,
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                api_key,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
            ],
            outputs=common_outputs,
        )
        batch_select.change(
            fn=select_batch_item,
            inputs=[batch_select, batch_state],
            outputs=[
                original_output,
                model_input_output,
                result_output,
                det_table,
                advice_box,
                quality_box,
                summary,
                chatbot,
                chat_state,
                export_file,
                export_path,
                report_file,
                report_path,
                export_report_btn,
                save_case_btn,
            ],
        )
        ai_enabled.change(fn=toggle_ai_settings, inputs=ai_enabled, outputs=ai_group)
        show_summary.change(fn=toggle_summary, inputs=show_summary, outputs=summary)
        enable_compare.change(fn=toggle_compare_options, inputs=[enable_compare, model_choice], outputs=model_choice)
        test_btn.click(
            fn=test_ai_settings,
            inputs=[
                ai_enabled,
                base_url,
                ai_model,
                key_mode,
                api_key,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
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
                api_key,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
            ],
            outputs=[settings_feedback, case_select, case_feedback],
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
                api_key,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
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
                api_key,
                save_key,
                auto_save,
                storage_dir,
                custom_prompt,
            ],
            outputs=[chatbot, chat_state, chat_input, export_file, export_path],
        )
        export_btn.click(fn=export_chat, inputs=[chat_state, storage_dir], outputs=[export_file, export_path])
        export_batch_btn.click(
            fn=export_batch_results,
            inputs=[batch_state, storage_dir],
            outputs=[batch_export_file, batch_export_path],
        )
        export_report_btn.click(
            fn=export_single_report,
            inputs=[batch_state, batch_select, storage_dir],
            outputs=[report_file, report_path],
        )
        save_case_btn.click(
            fn=save_case_record,
            inputs=[batch_state, batch_select, case_id, case_note, storage_dir],
            outputs=[case_feedback, case_select, case_detail],
        )
        refresh_case_btn.click(
            fn=refresh_case_records,
            inputs=storage_dir,
            outputs=[case_select, case_feedback],
        )
        case_select.change(
            fn=load_case_record,
            inputs=[case_select, storage_dir],
            outputs=case_detail,
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
    args = parse_args()
    build_app().launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        allowed_paths=[str(root) for root in _allowed_file_roots()],
    )
