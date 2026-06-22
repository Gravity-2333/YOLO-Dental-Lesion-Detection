from __future__ import annotations

import json
import math
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
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return _json_safe(value.item(), seen)
        except (AttributeError, TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return value
    except (TypeError, ValueError):
        return str(value)


def json_safe_value(value: Any) -> Any:
    return _json_safe(value)


def text_value(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value if value else fallback
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(json_safe_value(value), ensure_ascii=False, allow_nan=False)
    return str(value)
