from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any

import pandas as pd

from .history_store import HISTORY_TABLE_COLUMNS

CASE_TABLE_COLUMNS = ["保存时间", "病例编号", "图片名称", "检测数量", "涉及类别", "关注等级", "最高置信度", "文件名"]


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
        label_parts = [created_at, record_name]
        if case_id != "-" and image_name not in {"-", "当前单图", case_id}:
            label_parts.append(image_name)
        choice_parts.append((" · ".join(label_parts), file_name))

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
    return pd.DataFrame(rows, columns=HISTORY_TABLE_COLUMNS)


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
    return dataframe_table_html(case_table(rows), "当前患者暂无病例记录。")


def history_table_html(rows: list[dict[str, Any]]) -> str:
    return dataframe_table_html(history_table_from_rows(rows), "当前患者暂无检测历史。")


def history_choices_from_rows(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for row in rows:
        created_at = _short_choice_text(
            str(row.get("检测时间") or "").replace("T", " ", 1),
            32,
        )
        image_name = _short_choice_text(row.get("图片名称") or "未命名图片")
        record_id = str(row.get("记录ID") or "").strip()
        if record_id:
            label = created_at if image_name == "当前单图" else f"{created_at} · {image_name}"
            choices.append((label, record_id))
    return choices


def history_id(choice: str) -> str:
    value = str(choice or "").strip()
    return value.split("|")[-1].strip() if "|" in value else value
