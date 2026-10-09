from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any

import pandas as pd

CASE_TABLE_COLUMNS = ["保存时间", "病例编号", "图片名称", "检测数量", "涉及类别", "关注等级", "最高置信度"]
HISTORY_VIEW_COLUMNS = ["检测时间", "图片名称", "检测数量", "涉及类别", "最高置信度", "关注等级", "模型"]


def _short_choice_text(value: Any, max_length: int = 48) -> str:
    text = str(value or "").replace("|", "/").strip() or "-"
    return text if len(text) <= max_length else f"{text[: max_length - 1]}…"


def case_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    visible_rows = [{key: row.get(key, "") for key in CASE_TABLE_COLUMNS} for row in rows]
    return pd.DataFrame(visible_rows, columns=CASE_TABLE_COLUMNS)


def case_choices_from_rows(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    choice_parts: list[tuple[str, str]] = []
    for row in rows:
        file_name = str(row.get("文件名") or "").strip()
        if not file_name:
            continue
        created_at = _short_choice_text(
            str(row.get("保存时间") or "").replace("T", " ", 1),
            32,
        )
        case_id = _short_choice_text(row.get("病例编号") or "")
        image_name = _short_choice_text(row.get("图片名称") or "未命名图片")
        record_name = case_id if case_id != "-" else image_name
        if case_id != "-" and image_name not in {"-", "当前单图", case_id}:
            record_name += f" · {image_name}"
        data = row.get("_data") or {}
        state = "含影像" if data.get("case_format_version", 1) == 2 else "仅摘要"
        count = _integer(row.get("检测数量"))
        label = f"{record_name}\n{created_at} · {count} 个标记 · {state}"
        choice_parts.append((label, file_name))

    totals = Counter(label for label, _ in choice_parts)
    positions: Counter[str] = Counter()
    choices = []
    for base_label, file_name in choice_parts:
        label = base_label
        if totals[base_label] > 1:
            positions[base_label] += 1
            label = f"{base_label} {positions[base_label]}/{totals[base_label]}"
        choices.append((label, file_name))
    return choices


def history_table_from_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    visible_rows = [{key: row.get(key, "") for key in HISTORY_VIEW_COLUMNS} for row in rows]
    return pd.DataFrame(visible_rows, columns=HISTORY_VIEW_COLUMNS)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _record_overview_html(rows: list[dict[str, Any]], *, kind: str) -> str:
    total = len(rows)
    detection_total = sum(_integer(row.get("检测数量")) for row in rows)
    focus_total = sum("重点" in str(row.get("关注等级") or "") for row in rows)
    date_key = "保存时间" if kind == "case" else "检测时间"
    latest = str(rows[0].get(date_key) or "-").replace("T", " ", 1)[:16] if rows else "-"
    first_label = "病例总数" if kind == "case" else "检查次数"
    items = (
        (first_label, total, "当前筛选范围"),
        ("检测框", detection_total, "累计模型标记"),
        ("重点关注", focus_total, "建议优先复核"),
        ("最近记录", latest, "按时间倒序"),
    )
    cells = "".join(
        '<div class="record-stat">'
        f'<span>{escape(label)}</span><strong>{escape(str(value))}</strong>'
        f'<small>{escape(description)}</small></div>'
        for label, value, description in items
    )
    return f'<div class="record-stats" data-record-kind="{kind}">{cells}</div>'


def _history_tone(level: Any) -> str:
    text = str(level or "")
    if any(keyword in text for keyword in ("重点", "高", "紧急")):
        return "critical"
    if any(keyword in text for keyword in ("复核", "中")):
        return "review"
    if any(keyword in text for keyword in ("低", "轻")):
        return "low"
    return "clear"


def _history_queue_html(
    rows: list[dict[str, Any]],
    selected_id: str | None = None,
) -> str:
    if not rows:
        return (
            '<div class="history-queue-empty">'
            '<span aria-hidden="true">+</span><strong>暂无检查记录</strong>'
            '<p>完成检测后，记录会按时间倒序出现在这里。</p></div>'
        )

    selected = str(selected_id or "").strip()
    items: list[str] = []
    for index, row in enumerate(rows):
        record_id = str(row.get("记录ID") or "").strip()
        if not record_id:
            continue
        created_at = str(row.get("检测时间") or "-").replace("T", " ", 1)
        date_text, _, time_text = created_at.partition(" ")
        image_name = str(row.get("图片名称") or "未命名影像").strip()
        title = "当前检测" if image_name == "当前单图" else image_name
        count = _integer(row.get("检测数量"))
        level = str(row.get("关注等级") or "待复核").strip()
        classes = str(row.get("涉及类别") or "无明确类别").strip()
        tone = _history_tone(level)
        is_selected = record_id == selected or (not selected and index == 0)
        selected_class = " is-selected" if is_selected else ""
        items.append(
            '<button type="button" class="history-queue-item'
            f'{selected_class}" data-history-id="{escape(record_id, quote=True)}" '
            f'aria-pressed="{str(is_selected).lower()}">'
            '<span class="history-queue-rail" aria-hidden="true"><i></i></span>'
            '<span class="history-queue-copy">'
            f'<span class="history-queue-date">{escape(date_text)}'
            f'<small>{escape(time_text or "--:--")}</small></span>'
            f'<strong title="{escape(title, quote=True)}">{escape(title)}</strong>'
            f'<span class="history-queue-meta">{count} 个检测框 · {escape(classes)}</span>'
            '</span>'
            f'<span class="history-queue-status history-queue-status-{tone}">{escape(level)}</span>'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>'
            '</button>'
        )
    return (
        '<div class="history-queue" role="listbox" aria-label="检查记录">'
        + "".join(items)
        + "</div>"
    )


def dataframe_table_html(frame: pd.DataFrame, empty_message: str) -> str:
    if frame.empty:
        return f'<div class="record-table-empty">{escape(empty_message)}</div>'
    headers = "".join(f"<th>{escape(str(column))}</th>" for column in frame.columns)
    body = []
    for values in frame.itertuples(index=False, name=None):
        cells = "".join(
            f"<td>{escape('' if pd.isna(value) else str(value))}</td>"
            for value in values
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        '<div class="record-table-scroll"><table class="record-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def case_table_html(rows: list[dict[str, Any]]) -> str:
    table = dataframe_table_html(case_table(rows), "当前患者暂无病例记录。")
    return (
        _record_overview_html(rows, kind="case")
        + '<details class="record-data-view"><summary>查看病例数据表</summary>'
        + table
        + "</details>"
    )


def history_table_html(
    rows: list[dict[str, Any]],
    selected_id: str | None = None,
) -> str:
    table = dataframe_table_html(history_table_from_rows(rows), "当前患者暂无检测历史。")
    return (
        _record_overview_html(rows, kind="history")
        + '<div class="history-queue-heading"><div><span>REVIEW QUEUE</span>'
        '<h4>待审阅检查</h4></div><small>按时间倒序</small></div>'
        + _history_queue_html(rows, selected_id)
        + '<details class="record-data-view history-data-view"><summary>查看完整数据表</summary>'
        + table
        + "</details>"
    )


def history_choices_from_rows(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    choice_parts: list[tuple[str, str]] = []
    for row in rows:
        created_at = _short_choice_text(
            str(row.get("检测时间") or "").replace("T", " ", 1),
            32,
        )
        image_name = _short_choice_text(row.get("图片名称") or "未命名图片")
        record_id = str(row.get("记录ID") or "").strip()
        if record_id:
            title = "当前检测" if image_name == "当前单图" else image_name
            detection_count = _integer(row.get("检测数量"))
            level = _short_choice_text(row.get("关注等级") or "待复核", 18)
            label = f"{title}\n{created_at} · {detection_count} 个检测框 · {level}"
            choice_parts.append((label, record_id))

    totals = Counter(label for label, _ in choice_parts)
    positions: Counter[str] = Counter()
    choices = []
    for base_label, record_id in choice_parts:
        label = base_label
        if totals[base_label] > 1:
            positions[base_label] += 1
            label = f"{base_label} {positions[base_label]}/{totals[base_label]}"
        choices.append((label, record_id))
    return choices


def history_id(choice: str) -> str:
    value = str(choice or "").strip()
    return value.split("|")[-1].strip() if "|" in value else value
