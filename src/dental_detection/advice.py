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
            "content": (
                "请根据以下 YOLO 牙齿病变检测结果生成正式的影像复核意见。"
                "先确定优先级并合并同类信息，不要把检测框逐条换一种说法复述；"
                "只能使用下列文字数据，不得补写影像征象，也不得从坐标或粗略区域推断牙位及框间关系。\n"
                f"{summary}"
            ),
        },
    ]


def _confidence_sort_value(row: dict[str, Any]) -> float:
    confidence = parse_confidence(row.get("confidence"))
    return confidence if confidence is not None else -1.0


def _format_detection_evidence(items: list[dict[str, Any]]) -> str:
    evidence = []
    ordered = sorted(items, key=_confidence_sort_value, reverse=True)
    for item in ordered[:3]:
        region = str(item.get("图像区域") or "位置未提供")
        confidence = parse_confidence(item.get("confidence"))
        confidence_text = f"{confidence:.2f}" if confidence is not None else "未知"
        level = str(item.get("关注等级") or "待复核")
        evidence.append(f"{region}（{confidence_text}，{level}）")
    if len(ordered) > 3:
        evidence.append(f"另有 {len(ordered) - 3} 处同类标记")
    return "、".join(evidence)


def _combined_review_note(classes: set[str]) -> str:
    notes = []
    if {"Caries", "Impacted"}.issubset(classes):
        notes.append(
            "龋齿与阻生牙标记同时出现：请核对龋坏框是否涉及阻生牙邻牙，并评估是否存在清洁受限；"
            "仅凭当前检测框无法确认相邻关系或因果关系。"
        )
    if {"Caries", "Periapical Lesion"}.issubset(classes):
        notes.append(
            "龋齿与根尖周病变标记同时出现：请核对两类标记是否来自同一牙位，并结合牙髓活力和根尖片判断；"
            "当前信息无法确认二者关联。"
        )
    if {"Impacted", "Periapical Lesion"}.issubset(classes):
        notes.append(
            "阻生牙与根尖周病变标记同时出现：请分别确认来源牙位及解剖关系；当前信息无法确认二者关联。"
        )
    return " ".join(notes) or "暂无需要联合分析的类别组合。"


def default_advice(detections: list[dict[str, Any]]) -> str:
    detection_items = list(iter_detection_items(detections))
    if not detection_items:
        return (
            "【模型检出概况】本次未检测到明确的目标病变框，但未检出不等于排除病变，也可能受病变类型、"
            "影像质量或模型能力限制。\n\n"
            "【分区复核意见】若仍有疼痛、肿胀、冷热刺激痛、咬合不适或可见缺损，建议由牙科医生检查症状对应区域，"
            "不要仅凭本次未检出结果排除问题。\n\n"
            "【关联性评估】暂无需要联合分析的类别组合。\n\n"
            "【建议处置】建议携带原始影像就诊；由医生结合口内检查判断是否需要咬翼片、根尖片或其他检查。\n\n"
            "【风险提示与局限】如出现面部肿胀、发热、吞咽或呼吸困难、张口明显受限或持续加重的剧痛，"
            f"建议尽快就医。本系统不提供处方或治疗方案。{SAFETY_NOTICE}"
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for det in detection_items:
        if not has_detection_payload(det):
            continue
        row = enrich_detection_row(det)
        label = _normalize_class_name(str(row.get("class") or "未知区域"))
        grouped.setdefault(label, []).append(row)
    if not grouped:
        return default_advice([])

    ordered_groups = sorted(
        grouped.items(),
        key=lambda group: max((_confidence_sort_value(item) for item in group[1]), default=-1.0),
        reverse=True,
    )
    counts = []
    focus_lines = []
    for index, (normalized, items) in enumerate(ordered_groups[:3], start=1):
        advice = CLASS_ADVICE.get(
            normalized,
            "模型标记了待复核区域；请由医生结合原始影像、症状和口内检查确认其性质。",
        )
        display = CLASS_DISPLAY_NAMES.get(normalized, normalized)
        counts.append(f"{display} {len(items)} 处")
        focus_lines.append(f"{index}. {display}：{_format_detection_evidence(items)}。复核重点：{advice}")

    all_rows = [item for items in grouped.values() for item in items]
    first = max(all_rows, key=_confidence_sort_value)
    first_class = _normalize_class_name(str(first.get("class") or "未知区域"))
    first_display = CLASS_DISPLAY_NAMES.get(first_class, first_class)
    first_region = str(first.get("图像区域") or "位置未提供")
    first_confidence = parse_confidence(first.get("confidence"))
    first_confidence_text = f"{first_confidence:.2f}" if first_confidence is not None else "未知"
    low_confidence_note = ""
    if any(0 <= _confidence_sort_value(row) < 0.40 for row in all_rows):
        low_confidence_note = (
            " 低置信度标记可能受重叠结构、成像质量或伪影影响，应与高置信度结果分开判断。"
        )

    return "\n\n".join(
        [
            "【模型检出概况】模型共标记 "
            + str(len(all_rows))
            + " 处区域，包括"
            + "、".join(counts)
            + f"。首要复核为{first_region}的{first_display}标记（{first_confidence_text}）。"
            + "这只是模型排序，不是诊断；置信度不代表病变严重程度。",
            "【分区复核意见】\n" + "\n".join(focus_lines),
            "【关联性评估】" + _combined_review_note(set(grouped)),
            "【建议处置】建议携带原始影像和检测结果至口腔科，并说明疼痛性质、持续时间、冷热或咬合反应、"
            "是否反复肿胀等症状；具体检查由医生根据复核区域决定。",
            "【风险提示与局限】如出现面部肿胀、发热、吞咽或呼吸困难、张口明显受限或持续加重的剧痛，"
            "建议尽快就医。粗略图像区域不等同于专业牙位编号。"
            + low_confidence_note
            + " 本系统不提供处方、药物剂量或具体治疗方案。"
            + SAFETY_NOTICE,
        ]
    )
