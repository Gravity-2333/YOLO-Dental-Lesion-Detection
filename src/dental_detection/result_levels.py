from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any


CLASS_DISPLAY_NAMES = {
    "Caries": "龋齿",
    "Periapical Lesion": "根尖周病变",
    "Impacted": "阻生牙",
}

REGION_NOTICE = "区域提示仅根据图像中检测框位置粗略计算，不等同于专业牙位编号。"
DETECTION_CLASS_KEYS = {
    "class",
    "类别",
    "label",
    "name",
    "中文名称",
}
BBOX_KEYS = {"x1", "y1", "x2", "y2"}


def normalize_class_name(name: str) -> str:
    raw = str(name).replace("_", " ").strip()
    raw_key = re.sub(r"\s+", " ", raw.casefold())
    token = re.sub(r"[^a-z0-9]+", " ", raw.casefold()).strip()
    token = re.sub(r"\s+", " ", token)
    aliases = {
        "caries": "Caries",
        "龋齿": "Caries",
        "龋病": "Caries",
        "periapical lesion": "Periapical Lesion",
        "periapical lesions": "Periapical Lesion",
        "根尖周病变": "Periapical Lesion",
        "根尖周病损": "Periapical Lesion",
        "impacted": "Impacted",
        "impacted tooth": "Impacted",
        "impacted teeth": "Impacted",
        "阻生牙": "Impacted",
    }
    return aliases.get(raw_key, aliases.get(token, raw))


def get_class_display_name(name: str) -> str:
    normalized = normalize_class_name(name)
    return CLASS_DISPLAY_NAMES.get(normalized, str(name or "未知类别"))


def parse_confidence(value: Any) -> float | None:
    percent_value = False
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            percent_value = True
            value = text[:-1].strip()
        else:
            value = text
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if percent_value or number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))


def display_confidence(value: Any) -> float | str:
    confidence = parse_confidence(value)
    return round(confidence, 4) if confidence is not None else ""


def get_confidence_level(confidence: Any) -> str:
    value = parse_confidence(confidence)
    if value is None:
        return "未知"
    if value >= 0.70:
        return "重点关注"
    if value >= 0.40:
        return "建议复查"
    return "低置信度参考"


def get_confidence_description(confidence: Any) -> str:
    value = parse_confidence(confidence)
    if value is None:
        return "置信度为空或格式异常，仅保留原始检测提示。"
    if value >= 0.70:
        return "模型对该目标框较有把握，建议结合原始影像和医生检查重点复核。"
    if value >= 0.40:
        return "模型检测到可疑区域，但把握程度中等，建议由专业人员结合影像复核。"
    return "模型把握较低，仅作为提示，不应作为诊断依据。"


def has_detection_payload(det: Any) -> bool:
    if not isinstance(det, dict):
        return False
    for key in DETECTION_CLASS_KEYS:
        value = det.get(key)
        if value is not None and str(value).strip() != "":
            return True
    return all(det.get(key) is not None and str(det.get(key)).strip() != "" for key in BBOX_KEYS)


def iter_detection_items(detections: Any):
    if isinstance(detections, dict):
        candidates = (detections,)
    elif isinstance(detections, Iterable) and not isinstance(detections, (str, bytes, bytearray)):
        candidates = detections
    else:
        candidates = ()
    for item in candidates:
        if isinstance(item, dict):
            yield item


def estimate_image_region(det: dict[str, Any], image_size: tuple[int, int] | None = None) -> str:
    existing = str(det.get("图像区域") or det.get("image_region") or "").strip()
    if existing:
        return existing
    try:
        x1 = float(det.get("x1"))
        y1 = float(det.get("y1"))
        x2 = float(det.get("x2"))
        y2 = float(det.get("y2"))
    except (TypeError, ValueError):
        return ""
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return ""
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    if x2 <= x1 or y2 <= y1:
        return ""
    width, height = image_size or (None, None)
    try:
        width = float(width or det.get("image_width") or det.get("width") or 0)
        height = float(height or det.get("image_height") or det.get("height") or 0)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
        return ""
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    horizontal = "图像左侧" if center_x < width / 3 else "图像右侧" if center_x > width * 2 / 3 else "图像中部"
    vertical = "上方" if center_y < height / 2 else "下方"
    return f"{horizontal}{vertical}区域"


def enrich_detection_row(det: dict[str, Any], image_size: tuple[int, int] | None = None) -> dict[str, Any]:
    label = str(
        det.get("class")
        or det.get("类别")
        or det.get("label")
        or det.get("name")
        or det.get("中文名称")
        or "未知类别"
    )
    confidence = det.get("confidence", det.get("置信度", ""))
    return {
        "class": label,
        "中文名称": get_class_display_name(label),
        "confidence": display_confidence(confidence),
        "关注等级": get_confidence_level(confidence),
        "置信度解释": get_confidence_description(confidence),
        "图像区域": estimate_image_region(det, image_size),
        "x1": det.get("x1", ""),
        "y1": det.get("y1", ""),
        "x2": det.get("x2", ""),
        "y2": det.get("y2", ""),
    }
