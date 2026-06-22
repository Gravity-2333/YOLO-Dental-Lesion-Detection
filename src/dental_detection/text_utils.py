from __future__ import annotations

import json
from typing import Any


def _json_safe(value: Any, seen: set[int] | None = None) -> Any:
    seen = seen or set()
    if isinstance(value, dict):
        marker = id(value)
        if marker in seen:
            return "<recursive>"
        seen.add(marker)
        try:
            return {str(key): _json_safe(item, seen) for key, item in value.items()}
        finally:
            seen.discard(marker)
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in seen:
            return "<recursive>"
        seen.add(marker)
        try:
            return [_json_safe(item, seen) for item in value]
        finally:
            seen.discard(marker)
    if isinstance(value, set):
        marker = id(value)
        if marker in seen:
            return "<recursive>"
        seen.add(marker)
        try:
            return sorted((_json_safe(item, seen) for item in value), key=str)
        finally:
            seen.discard(marker)
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return str(value)


def text_value(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value if value else fallback
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(_json_safe(value), ensure_ascii=False)
    return str(value)
