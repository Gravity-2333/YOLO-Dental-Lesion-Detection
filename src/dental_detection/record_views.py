from __future__ import annotations

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


def case_choices_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [
        f"{_short_choice_text(row.get('保存时间') or '', 32)} | "
        f"{_short_choice_text(row.get('病例编号') or row.get('文件名'))} | "
        f"{_short_choice_text(row.get('图片名称') or '未命名图片')} | {row.get('文件名')}"
        for row in rows
    ]


def history_table_from_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=HISTORY_TABLE_COLUMNS)


def history_choices_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    choices = []
    for row in rows:
        created_at = _short_choice_text(row.get("检测时间") or "", 32)
        image_name = _short_choice_text(row.get("图片名称") or "未命名图片")
        record_id = row.get("记录ID", "")
        if record_id:
            choices.append(f"{created_at} | {image_name} | {record_id}")
    return choices


def history_id(choice: str) -> str:
    return str(choice or "").split("|")[-1].strip()
