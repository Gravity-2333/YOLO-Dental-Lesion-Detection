from __future__ import annotations

import json
from typing import Any


def text_value(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)
