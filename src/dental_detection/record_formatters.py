from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from .ai_defaults import SAFETY_NOTICE
from .result_items import iter_model_result_items, model_result_detections, model_result_name, model_result_path
from .result_levels import enrich_detection_row, has_detection_payload, iter_detection_items
from .text_utils import text_value


def _clean_detection_records(detections: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for det in iter_detection_items(detections):
        if not has_detection_payload(det):
            continue
        row = enrich_detection_row(det)
        model_name = det.get("model") or det.get("模型")
        if model_name:
            row["模型"] = text_value(model_name)
        if not all(value in {"", None} for value in row.values()):
            rows.append(row)
    return rows


def _model_result_detections(model_results: Any) -> list[dict[str, Any]]:
    model_items = list(iter_model_result_items(model_results))
    if not model_items:
        return []
    rows: list[dict[str, Any]] = []
    for item in model_items:
        model = model_result_name(item, "")
        for det in iter_detection_items(model_result_detections(item)):
            if not has_detection_payload(det):
                continue
            row = dict(det)
            if model and not row.get("模型"):
                row["模型"] = model
            rows.append(row)
    return _clean_detection_records(rows)


def _record_detections(data: dict[str, Any]) -> list[dict[str, Any]]:
    model_rows = _model_result_detections(data.get("model_results"))
    if model_rows:
        return model_rows
    return _clean_detection_records(data.get("detections"))


def _path_artifact_name(value: Any) -> str:
    path_text = text_value(value).strip().rstrip("/\\")
    if not path_text:
        return ""
    path_type = PureWindowsPath if "\\" in path_text else PurePosixPath
    return path_type(path_text).name


def _suggestion_source_label(value: Any) -> str:
    source = text_value(value, "default").strip()
    return {"default": "内置建议", "ai": "AI 建议"}.get(source.casefold(), source)


def _model_display_name(value: Any, fallback: str = "未记录") -> str:
    model = text_value(value).strip()
    return fallback if not model or model.casefold() == "unknown" else model


def _format_model_results(model_results: Any) -> list[str]:
    model_items = list(iter_model_result_items(model_results))
    if not model_items:
        return []
    lines = ["", "模型结果明细："]
    for index, item in enumerate(model_items, start=1):
        model = _model_display_name(model_result_name(item, f"模型 {index}"), f"模型 {index}")
        raw_count = item.get("detection_count", item.get("检测数量"))
        if raw_count in {"", None}:
            raw_count = sum(1 for _ in iter_detection_items(model_result_detections(item)))
        count = text_value(raw_count, "0")
        artifact_name = _path_artifact_name(model_result_path(item))
        line = f"{index}. {model} | 检测数量={count}"
        if artifact_name:
            line += f" | 模型文件={artifact_name}"
        lines.append(line)
    return lines if len(lines) > 2 else []


def _format_summary_value(key: str, value: Any) -> list[str]:
    if key == "模型结果" and isinstance(value, list):
        lines = ["- 模型结果:"]
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                model = _model_display_name(
                    item.get("模型") or item.get("model"),
                    f"模型 {index}",
                )
                count = item.get("检测数量", item.get("count", "-"))
                artifact_name = _path_artifact_name(
                    item.get("路径") or item.get("模型路径") or item.get("model_path")
                )
                line = f"  {index}. {model} | 检测数量={count}"
                if artifact_name:
                    line += f" | 模型文件={artifact_name}"
                lines.append(line)
            else:
                lines.append(f"  {index}. {item}")
        return lines
    if isinstance(value, dict):
        lines = [f"- {key}:"]
        lines.extend(f"  {sub_key}: {sub_value}" for sub_key, sub_value in value.items())
        return lines
    if isinstance(value, list):
        lines = [f"- {key}:"]
        lines.extend(f"  {index}. {item}" for index, item in enumerate(value, start=1))
        return lines
    return [f"- {key}: {value}"]


def format_case_record(data: dict[str, Any] | None) -> str:
    if not data:
        return "暂无病例详情。选择已保存病例后，会在这里显示检测摘要、检测框和辅助建议。"
    if "错误" in data:
        return str(data["错误"])
    if "提示" in data:
        return str(data["提示"])

    summary = data.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    detections = _record_detections(data)
    lines = [
        f"病例编号：{text_value(data.get('case_id'), '未填写')}",
        f"保存时间：{text_value(data.get('created_at'), '-')}",
        f"图片名称：{text_value(data.get('image_name'), '-')}",
        f"建议来源：{_suggestion_source_label(data.get('suggestion_type'))}",
    ]
    display_name = text_value(data.get("display_name")).strip()
    image_name = text_value(data.get("image_name")).strip()
    if display_name and display_name != image_name:
        lines.insert(3, f"列表显示名：{display_name}")
    note = data.get("note")
    if note:
        lines.append(f"病例备注：{text_value(note)}")
    report_path = data.get("report_path") or data.get("word_report_path") or data.get("zip_report_path")
    if report_path:
        lines.append(f"报告文件：{_path_artifact_name(report_path)}")
    lines.extend(_format_model_results(data.get("model_results")))

    lines.extend(["", "检测摘要："])
    if summary:
        for key, value in summary.items():
            lines.extend(_format_summary_value(str(key), value))
    else:
        lines.append("- 暂无摘要信息")

    lines.extend(["", f"检测框：共 {len(detections)} 个"])
    if detections:
        for index, det in enumerate(detections, start=1):
            display_name = det.get("中文名称") or det.get("class", "-")
            attention = det.get("关注等级") or "-"
            lines.append(
                f"{index}. {det.get('class', '-')}"
                f"（{display_name}）"
                f"{' | 模型=' + text_value(det.get('模型')) if det.get('模型') else ''}"
                f" | confidence={det.get('confidence', '-')}"
                f" | 关注等级={attention}"
                f" | 图像区域={det.get('图像区域', '') or '未计算'}"
                f" | bbox=({det.get('x1', '-')}, {det.get('y1', '-')}, {det.get('x2', '-')}, {det.get('y2', '-')})"
            )
    else:
        lines.append("- 未检测到病变框")

    quality_text = data.get("quality_text")
    if quality_text:
        lines.extend(["", "图像质量提示：", str(quality_text)])

    suggestion = data.get("suggestion")
    if suggestion:
        lines.extend(["", "辅助建议：", suggestion])
    notice = data.get("safety_notice") or SAFETY_NOTICE
    if notice and text_value(notice).strip() not in text_value(suggestion):
        lines.extend(["", notice])
    return "\n".join(lines)


def format_history_record(record: dict[str, Any] | None) -> str:
    if not record:
        return "请选择一条检测历史。"
    detections = _record_detections(record)
    classes = record.get("classes")
    if isinstance(classes, str):
        class_text = classes.strip() or "无"
    elif isinstance(classes, (list, tuple, set)):
        class_text = "、".join(text_value(item).strip() for item in classes if text_value(item).strip()) or "无"
    else:
        class_text = "无"
    report_name = _path_artifact_name(record.get("report_path")) or "暂无"
    lines = [
        f"检测时间：{text_value(record.get('created_at'))}",
        f"图片名称：{text_value(record.get('image_name'))}",
        f"模型：{_model_display_name(record.get('model'))}",
        f"CLAHE 增强：{'是' if record.get('use_clahe') else '否'}",
        f"检测数量：{text_value(record.get('detection_count'), '0')}",
        f"涉及类别：{class_text}",
        f"最高置信度：{text_value(record.get('max_confidence'), '无')}",
        f"关注等级：{text_value(record.get('level'))}",
        f"报告文件：{report_name}",
    ]
    display_name = text_value(record.get("display_name")).strip()
    image_name = text_value(record.get("image_name")).strip()
    if display_name and display_name != image_name:
        lines.insert(2, f"列表显示名：{display_name}")
    lines.extend(_format_model_results(record.get("model_results")))
    lines.extend(["", "检测框明细："])
    if detections:
        for index, det in enumerate(detections, start=1):
            lines.append(
                f"{index}. {det.get('中文名称', det.get('class', '未知类别'))} "
                f"{'model=' + text_value(det.get('模型')) + ' ' if det.get('模型') else ''}"
                f"confidence={det.get('confidence', '')} "
                f"region={det.get('图像区域', '') or '未计算'} "
                f"bbox=({det.get('x1', '')}, {det.get('y1', '')}, {det.get('x2', '')}, {det.get('y2', '')})"
            )
    else:
        lines.append("无检测框。")
    advice = text_value(record.get("advice")).strip()
    if advice:
        lines.extend(["", "辅助建议：", advice])
    return "\n".join(lines)
