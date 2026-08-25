from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT


EXAMPLE_DIR = PROJECT_ROOT / "assets" / "examples" / "dental"
EXAMPLE_META_PATH = EXAMPLE_DIR / "示例图片说明.json"


def load_example_metadata() -> list[dict[str, Any]]:
    if not EXAMPLE_META_PATH.exists():
        return []
    try:
        data = json.loads(EXAMPLE_META_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    items: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        file_name = Path(str(item.get("文件名") or "")).name
        path = EXAMPLE_DIR / file_name
        if file_name and path.exists():
            items.append({**item, "path": path})
    return items


def example_choices() -> list[tuple[str, str]]:
    return [
        (
            str(item.get("示例名称") or item.get("文件名") or item["path"].name),
            str(item["path"]),
        )
        for item in load_example_metadata()
    ]


def example_preview_text(path_text: str | None) -> str:
    if not path_text:
        return "选择示例后会在这里显示说明。"

    target = Path(path_text)
    for item in load_example_metadata():
        if item["path"] != target:
            continue
        lines = [
            f"示例名称：{item.get('示例名称', target.name)}",
            f"示意主题：{item.get('示意主题', '通用流程')}",
            f"脱敏状态：{item.get('是否脱敏', '是')}",
        ]
        marker_notice = str(item.get("素材标记说明") or "").strip()
        if marker_notice:
            lines.append(f"素材标记：{marker_notice}")
        description = str(item.get("说明文本") or "").strip()
        if description:
            lines.append(description)
        return "\n".join(lines)
    return "未找到该示例说明。"
