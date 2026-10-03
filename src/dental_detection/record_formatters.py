from __future__ import annotations

from html import escape
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


def _html_text(value: Any, fallback: str = "-") -> str:
    text = text_value(value).strip() or fallback
    return escape(text)


def _html_paragraphs(value: Any) -> str:
    text = text_value(value).strip()
    if not text:
        return '<p class="record-empty-copy">暂无内容。</p>'
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    return "".join(f"<p>{escape(part)}</p>" for part in paragraphs)


def _attention_tone(value: Any) -> tuple[str, str]:
    label = text_value(value, "无检测结果").strip() or "无检测结果"
    if "重点" in label:
        return "critical", label
    if "复查" in label:
        return "review", label
    if "低置信" in label:
        return "low", label
    return "clear", label


def _detail_empty(title: str, message: str) -> str:
    return (
        '<div class="record-detail-empty">'
        '<span class="record-detail-empty-mark" aria-hidden="true">+</span>'
        f"<h3>{escape(title)}</h3><p>{escape(message)}</p>"
        "</div>"
    )


def _record_meta_html(items: list[tuple[str, Any]]) -> str:
    cells = "".join(
        '<div class="record-meta-item">'
        f'<span>{escape(label)}</span><strong>{_html_text(value)}</strong>'
        "</div>"
        for label, value in items
    )
    return f'<div class="record-meta-grid">{cells}</div>'


def _model_summary_html(model_results: Any) -> str:
    items = list(iter_model_result_items(model_results))
    if not items:
        return ""
    rows = []
    for index, item in enumerate(items, start=1):
        model = _model_display_name(model_result_name(item, f"模型 {index}"), f"模型 {index}")
        detections = list(iter_detection_items(model_result_detections(item)))
        rows.append(
            '<div class="record-model-row">'
            f'<span class="record-model-index">{index:02d}</span>'
            f'<strong>{escape(model)}</strong><span>{len(detections)} 个检测框</span>'
            "</div>"
        )
    return (
        '<section class="record-detail-section"><div class="record-section-heading">'
        '<div><span>MODEL REVIEW</span><h4>模型结果</h4></div></div>'
        f'<div class="record-model-list">{"".join(rows)}</div></section>'
    )


def _detection_table_html(detections: list[dict[str, Any]]) -> str:
    if not detections:
        return '<div class="record-detail-note is-clear">当前记录没有检测框。</div>'
    page_size = 8
    rows = []
    for index, det in enumerate(detections, start=1):
        class_name = det.get("中文名称") or det.get("class") or "未知类别"
        confidence = det.get("confidence", "-")
        try:
            confidence_text = f"{float(confidence):.2f}"
        except (TypeError, ValueError):
            confidence_text = text_value(confidence, "-")
        tone, attention = _attention_tone(det.get("关注等级"))
        coordinate_items = tuple(
            (key.upper(), text_value(det.get(key), "-"))
            for key in ("x1", "y1", "x2", "y2")
        )
        coordinate_cells = "".join(
            '<div class="record-coordinate-value">'
            f'<span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
            for label, value in coordinate_items
        )
        hidden = " hidden" if index > page_size else ""
        rows.append(
            f'<tr class="record-detection-row" data-row-index="{index}"{hidden}>'
            f'<td class="record-index-cell">{index:02d}</td>'
            f"<td><strong>{_html_text(class_name)}</strong>"
            f'<span class="record-cell-subtext">{_html_text(det.get("模型"), "未记录模型")}</span></td>'
            '<td class="record-assessment-cell">'
            f'<span class="record-status record-status-{tone}">{escape(attention)}</span>'
            f'<span class="record-confidence">置信度 {escape(confidence_text)}</span></td>'
            f"<td>{_html_text(det.get('图像区域'), '未计算')}</td>"
            '<td><button type="button" class="record-coordinate-trigger" '
            'aria-expanded="false">查看坐标</button></td>'
            "</tr>"
            f'<tr class="record-coordinate-row" data-row-index="{index}" hidden>'
            '<td colspan="5"><div class="record-coordinate-panel">'
            '<div class="record-coordinate-heading"><span>BOUNDING BOX</span>'
            f'<strong>{_html_text(class_name)} · 检测框 {index:02d}</strong></div>'
            f'<div class="record-coordinate-grid">{coordinate_cells}</div>'
            "</div></td></tr>"
        )
    total_pages = max(1, (len(detections) + page_size - 1) // page_size)
    next_disabled = " disabled" if total_pages == 1 else ""
    return (
        f'<div class="record-detection-grid" data-page-size="{page_size}" data-current-page="1">'
        '<div class="record-detection-table-wrap"><table class="record-detection-table">'
        "<thead><tr><th>#</th><th>类别 / 模型</th><th>模型研判</th>"
        "<th>图像区域</th><th>详情</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        '<div class="record-table-pagination" role="navigation" aria-label="检测明细分页">'
        f'<span class="record-page-status" aria-live="polite">第 1 / {total_pages} 页 · 共 {len(detections)} 项</span>'
        '<div class="record-page-actions">'
        '<button type="button" class="record-page-button" data-page-action="previous" '
        'aria-label="上一页" title="上一页" disabled>‹</button>'
        f'<span class="record-page-number">1 / {total_pages}</span>'
        '<button type="button" class="record-page-button" data-page-action="next" '
        f'aria-label="下一页" title="下一页"{next_disabled}>›</button>'
        "</div></div></div>"
    )


def case_record_detail_html(data: dict[str, Any] | None) -> str:
    if not data:
        return _detail_empty("选择一条病例", "病例摘要、检测明细、医生备注与辅助建议将在这里集中显示。")
    if "错误" in data:
        return _detail_empty("病例无法读取", text_value(data.get("错误")))
    if "提示" in data:
        return _detail_empty("暂无病例详情", text_value(data.get("提示")))

    detections = _record_detections(data)
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    level = summary.get("关注等级") or next(
        (row.get("关注等级") for row in detections if row.get("关注等级")),
        "无检测结果",
    )
    tone, level_label = _attention_tone(level)
    title = text_value(data.get("case_id"), "未命名病例")
    image_name = data.get("display_name") or data.get("image_name") or "未命名影像"
    note = text_value(data.get("note")).strip()
    suggestion = data.get("suggestion")
    return (
        '<article class="record-detail-sheet">'
        '<header class="record-detail-header"><div>'
        '<span class="record-detail-kicker">CASE REVIEW</span>'
        f"<h3>{escape(title)}</h3><p>{_html_text(image_name)}</p></div>"
        f'<span class="record-status record-status-{tone}">{escape(level_label)}</span></header>'
        + _record_meta_html(
            [
                ("保存时间", data.get("created_at")),
                ("检测框", len(detections)),
                ("建议来源", _suggestion_source_label(data.get("suggestion_type"))),
                ("报告", _path_artifact_name(data.get("report_path") or data.get("word_report_path")) or "未生成"),
            ]
        )
        + (
            '<section class="record-detail-section"><div class="record-section-heading">'
            '<div><span>CLINICAL NOTE</span><h4>医生备注</h4></div></div>'
            f'<div class="record-detail-note">{_html_paragraphs(note)}</div></section>'
            if note
            else ""
        )
        + _model_summary_html(data.get("model_results"))
        + '<section class="record-detail-section"><div class="record-section-heading"><div>'
        f'<span>DETECTIONS · {len(detections):02d}</span><h4>检测明细</h4></div></div>'
        + _detection_table_html(detections)
        + "</section>"
        + '<section class="record-detail-section"><div class="record-section-heading"><div>'
        '<span>ASSISTIVE SUMMARY</span><h4>辅助建议</h4></div></div>'
        f'<div class="record-advice">{_html_paragraphs(suggestion)}</div></section>'
        '<footer class="record-safety-note">模型结果仅供辅助参考，需由专业牙科医生结合原始影像复核。</footer>'
        "</article>"
    )


def history_record_detail_html(record: dict[str, Any] | None) -> str:
    if not record:
        return _detail_empty("选择一次检查", "从左侧时间序列中选择记录后，可在这里审阅模型结果和检测框。")
    detections = _record_detections(record)
    tone, level_label = _attention_tone(record.get("level"))
    classes = record.get("classes")
    if isinstance(classes, (list, tuple, set)):
        class_text = "、".join(text_value(item) for item in classes if text_value(item).strip()) or "无"
    else:
        class_text = text_value(classes, "无")
    title = record.get("display_name") or record.get("image_name") or "未命名影像"
    advice = record.get("advice")
    return (
        '<article class="record-detail-sheet">'
        '<header class="record-detail-header"><div>'
        '<span class="record-detail-kicker">DETECTION REVIEW</span>'
        f"<h3>{_html_text(title)}</h3><p>{_html_text(record.get('created_at'))}</p></div>"
        f'<span class="record-status record-status-{tone}">{escape(level_label)}</span></header>'
        + _record_meta_html(
            [
                ("检测数量", record.get("detection_count", len(detections))),
                ("涉及类别", class_text),
                ("最高置信度", record.get("max_confidence", "无")),
                ("CLAHE", "已启用" if record.get("use_clahe") else "未启用"),
            ]
        )
        + _model_summary_html(record.get("model_results"))
        + '<section class="record-detail-section"><div class="record-section-heading"><div>'
        f'<span>DETECTIONS · {len(detections):02d}</span><h4>检测明细</h4></div></div>'
        + _detection_table_html(detections)
        + "</section>"
        + '<section class="record-detail-section"><div class="record-section-heading"><div>'
        '<span>ASSISTIVE SUMMARY</span><h4>辅助建议</h4></div></div>'
        f'<div class="record-advice">{_html_paragraphs(advice)}</div></section>'
        '<footer class="record-safety-note">历史结果用于回顾与复核，不替代专业牙科医生诊断。</footer>'
        "</article>"
    )
