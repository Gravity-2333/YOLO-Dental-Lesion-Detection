from __future__ import annotations

from typing import Any

from .assistant import SAFETY_NOTICE
from .result_levels import enrich_detection_row
from .text_utils import text_value


def _clean_detection_records(detections: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for det in detections or []:
        if isinstance(det, dict):
            row = enrich_detection_row(det)
            model_name = det.get("model") or det.get("模型")
            if model_name:
                row["模型"] = text_value(model_name)
            if not all(value in {"", None} for value in row.values()):
                rows.append(row)
    return rows


def _model_result_detections(model_results: Any) -> list[dict[str, Any]]:
    if not isinstance(model_results, list) or not model_results:
        return []
    rows: list[dict[str, Any]] = []
    for item in model_results:
        if not isinstance(item, dict):
            continue
        model = item.get("model") or item.get("模型")
        for det in item.get("detections") or []:
            if not isinstance(det, dict):
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
    return _clean_detection_records(data.get("detections") or [])


def _format_model_results(model_results: Any) -> list[str]:
    if not isinstance(model_results, list) or not model_results:
        return []
    lines = ["", "模型结果明细："]
    for index, item in enumerate(model_results, start=1):
        if not isinstance(item, dict):
            continue
        model = text_value(item.get("model") or item.get("模型"), f"模型 {index}")
        count = text_value(item.get("detection_count") or item.get("检测数量"), "0")
        path = text_value(item.get("model_path") or item.get("路径") or item.get("模型路径"))
        line = f"- {index}. {model} | 检测数量={count}"
        if path:
            line += f" | 路径={path}"
        lines.append(line)
    return lines if len(lines) > 2 else []


def _format_summary_value(key: str, value: Any) -> list[str]:
    if key == "模型结果" and isinstance(value, list):
        lines = ["- 模型结果:"]
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                model = item.get("模型") or item.get("model") or f"模型 {index}"
                count = item.get("检测数量", item.get("count", "-"))
                path = item.get("路径") or item.get("模型路径") or item.get("model_path")
                line = f"  {index}. {model} | 检测数量={count}"
                if path:
                    line += f" | 路径={path}"
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

    summary = data.get("summary") or {}
    detections = _record_detections(data)
    lines = [
        f"病例编号：{text_value(data.get('case_id'), '未填写')}",
        f"保存时间：{text_value(data.get('created_at'), '-')}",
        f"图片名称：{text_value(data.get('image_name'), '-')}",
        f"建议来源：{text_value(data.get('suggestion_type'), 'default')}",
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
        lines.append(f"报告路径：{report_path}")
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
                "- "
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
    if notice:
        lines.extend(["", notice])
    return "\n".join(lines)


def format_history_record(record: dict[str, Any] | None) -> str:
    if not record:
        return "请选择一条检测历史。"
    detections = _clean_detection_records(record.get("detections") or [])
    classes = record.get("classes")
    if isinstance(classes, str):
        class_text = classes.strip() or "无"
    elif isinstance(classes, (list, tuple, set)):
        class_text = "、".join(text_value(item).strip() for item in classes if text_value(item).strip()) or "无"
    else:
        class_text = "无"
    lines = [
        f"检测时间：{text_value(record.get('created_at'))}",
        f"图片名称：{text_value(record.get('image_name'))}",
        f"模型：{text_value(record.get('model'))}",
        f"CLAHE 增强：{'是' if record.get('use_clahe') else '否'}",
        f"检测数量：{text_value(record.get('detection_count'), '0')}",
        f"涉及类别：{class_text}",
        f"最高置信度：{text_value(record.get('max_confidence'), '无')}",
        f"关注等级：{text_value(record.get('level'))}",
        f"报告路径：{text_value(record.get('report_path'), '暂无')}",
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
