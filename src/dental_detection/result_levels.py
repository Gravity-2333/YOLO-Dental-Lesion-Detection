from __future__ import annotations

import re
from typing import Any


CLASS_DISPLAY_NAMES = {
    "Caries": "龋齿",
    "Periapical Lesion": "根尖周病变",
    "Impacted": "阻生牙",
}


def normalize_class_name(name: str) -> str:
    token = re.sub(r"[^a-z0-9]+", " ", str(name).casefold()).strip()
    token = re.sub(r"\s+", " ", token)
    aliases = {
        "caries": "Caries",
        "periapical lesion": "Periapical Lesion",
        "periapical lesions": "Periapical Lesion",
        "impacted": "Impacted",
        "impacted tooth": "Impacted",
        "impacted teeth": "Impacted",
    }
    return aliases.get(token, str(name).replace("_", " ").strip())


def get_class_display_name(name: str) -> str:
    normalized = normalize_class_name(name)
    return CLASS_DISPLAY_NAMES.get(normalized, str(name or "未知类别"))


def parse_confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number))


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


def enrich_detection_row(det: dict[str, Any]) -> dict[str, Any]:
    label = str(det.get("class", "未知类别") or "未知类别")
    confidence = det.get("confidence", "")
    return {
        "class": label,
        "中文名称": get_class_display_name(label),
        "confidence": confidence,
        "关注等级": get_confidence_level(confidence),
        "置信度解释": get_confidence_description(confidence),
        "x1": det.get("x1", ""),
        "y1": det.get("y1", ""),
        "x2": det.get("x2", ""),
        "y2": det.get("y2", ""),
    }
