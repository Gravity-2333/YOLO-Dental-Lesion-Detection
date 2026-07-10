from __future__ import annotations

import json
from typing import Any

from .ai_defaults import CLASS_ADVICE, DEFAULT_AI_PROMPT, SAFETY_NOTICE
from .result_levels import (
    CLASS_DISPLAY_NAMES,
    enrich_detection_row,
    has_detection_payload,
    iter_detection_items,
    normalize_class_name,
    parse_confidence,
)
from .text_utils import json_safe_value


_normalize_class_name = normalize_class_name


def _prompt_safe_detections(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_rows: list[dict[str, Any]] = []
    for row in iter_detection_items(json_safe_value(detections)):
        item = dict(row)
        if "confidence" in item:
            confidence = parse_confidence(item.get("confidence"))
            item["confidence"] = round(confidence, 4) if confidence is not None else ""
        safe_rows.append(item)
    return safe_rows


def detection_prompt(
    detections: list[dict[str, Any]], custom_prompt: str | None = None
) -> list[dict[str, str]]:
    summary = json.dumps(_prompt_safe_detections(detections), ensure_ascii=False, indent=2, allow_nan=False)
    system_prompt = (custom_prompt or "").strip() or DEFAULT_AI_PROMPT
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": f"请根据以下 YOLO 牙齿病变检测结果生成简洁建议：\n{summary}",
        },
    ]


def default_advice(detections: list[dict[str, Any]]) -> str:
    detection_items = list(iter_detection_items(detections))
    if not detection_items:
        return (
            "检测摘要：本次未检测到明确的目标病变框。\n\n"
            "需要关注的位置：未形成可定位的检测框；若原始影像存在可疑区域，应以专业阅片为准。\n\n"
            "复查建议：如仍有疼痛、肿胀、冷热刺激痛或影像质量较差，建议携带原始牙片咨询专业牙科医生复核。\n\n"
            "注意事项：未检测到目标不代表不存在病变，本系统不提供治疗方案、处方或药物剂量建议。\n\n"
            f"安全声明：{SAFETY_NOTICE}"
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for det in detection_items:
        if not has_detection_payload(det):
            continue
        row = enrich_detection_row(det)
        label = str(row.get("class") or "未知区域")
        grouped.setdefault(label, []).append(row)
    if not grouped:
        return default_advice([])

    summary_lines = []
    focus_lines = []
    for label, items in sorted(grouped.items()):
        confidences = []
        for item in items:
            confidence = parse_confidence(item.get("confidence"))
            if confidence is not None:
                confidences.append(confidence)
        high_conf = max(confidences) if confidences else None
        if high_conf is None:
            level = "置信度未知，仅供参考"
            confidence_text = "未知"
        elif high_conf >= 0.70:
            level = "重点关注"
            confidence_text = f"{high_conf:.2f}"
        elif high_conf >= 0.40:
            level = "建议复查确认"
            confidence_text = f"{high_conf:.2f}"
        else:
            level = "低置信度，仅供参考"
            confidence_text = f"{high_conf:.2f}"

        normalized = _normalize_class_name(label)
        advice = CLASS_ADVICE.get(
            normalized,
            CLASS_ADVICE.get(
                label,
                "检测到模型标记的可疑区域。建议结合原始影像、症状和医生检查进行复核。",
            ),
        )
        display = CLASS_DISPLAY_NAMES.get(normalized, label)
        summary_lines.append(f"{display} {len(items)} 处，最高置信度约 {confidence_text}，{level}。")
        focus_lines.append(f"{display}：{advice}")

    return "\n\n".join(
        [
            "检测摘要：" + " ".join(summary_lines),
            "需要关注的位置：" + " ".join(focus_lines),
            "复查建议：请保留原始影像和检测结果，必要时携带给专业牙科医生复查确认。",
            "注意事项：本建议不构成最终诊断，不提供治疗方案、处方或具体药物剂量。置信度不等同于疾病严重程度。",
            f"安全声明：{SAFETY_NOTICE}",
        ]
    )
