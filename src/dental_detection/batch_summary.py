from __future__ import annotations

from collections import defaultdict
from typing import Any

from .result_levels import (
    get_class_display_name,
    get_confidence_level,
    parse_confidence,
)


def _iter_model_results(item: dict[str, Any]):
    results = item.get("all_results")
    if isinstance(results, list) and results:
        for result in results:
            if isinstance(result, dict):
                yield result
        return
    result = item.get("result") or item
    if isinstance(result, dict):
        yield result


def _clean_detections(detections: Any) -> list[dict[str, Any]]:
    rows = []
    for det in detections or []:
        if isinstance(det, dict):
            rows.append(det)
    return rows


def build_batch_summary(batch_state: list[dict[str, Any]], batch_errors: list[str] | None = None) -> dict[str, Any]:
    errors = list(batch_errors or [])
    class_stats: dict[str, dict[str, Any]] = {}
    image_rows = []
    no_detection_images = []
    total_boxes = 0
    confidences = []

    for item in batch_state or []:
        image_name = item.get("name") or item.get("image_name") or "未命名图片"
        image_detections = []
        for result in _iter_model_results(item):
            for det in _clean_detections(result.get("detections", [])):
                image_detections.append(det)
                total_boxes += 1
                label = str(det.get("class", "未知类别") or "未知类别")
                confidence = parse_confidence(det.get("confidence"))
                if confidence is not None:
                    confidences.append(confidence)
                stat = class_stats.setdefault(
                    label,
                    {
                        "类别": label,
                        "中文名称": get_class_display_name(label),
                        "检测框数量": 0,
                        "涉及图片": set(),
                        "最高置信度": 0.0,
                        "置信度列表": [],
                    },
                )
                stat["检测框数量"] += 1
                stat["涉及图片"].add(image_name)
                if confidence is not None:
                    stat["最高置信度"] = max(stat["最高置信度"], confidence)
                    stat["置信度列表"].append(confidence)

        if image_detections:
            scored = [
                (parse_confidence(det.get("confidence")) or 0.0, str(det.get("class", "未知类别") or "未知类别"))
                for det in image_detections
            ]
            highest_confidence, highest_class = max(scored, key=lambda pair: pair[0])
            image_rows.append(
                {
                    "图片名称": image_name,
                    "最高类别": highest_class,
                    "最高置信度": round(highest_confidence, 4),
                    "检测框数量": len(image_detections),
                    "关注等级": get_confidence_level(highest_confidence),
                }
            )
        else:
            no_detection_images.append(image_name)

    class_rows = []
    for stat in class_stats.values():
        confidence_list = stat.pop("置信度列表")
        images = stat.pop("涉及图片")
        average = sum(confidence_list) / len(confidence_list) if confidence_list else 0.0
        class_rows.append(
            {
                **stat,
                "涉及图片数": len(images),
                "最高置信度": round(stat["最高置信度"], 4),
                "平均置信度": round(average, 4),
            }
        )
    class_rows.sort(key=lambda row: (-row["检测框数量"], row["类别"]))
    focus_rows = sorted(
        image_rows,
        key=lambda row: (-float(row["最高置信度"]), -int(row["检测框数量"]), row["图片名称"]),
    )
    for index, row in enumerate(focus_rows, start=1):
        row["排名"] = index

    return {
        "图片总数": len(batch_state or []) + len(errors),
        "成功处理": len(batch_state or []),
        "处理失败": len(errors),
        "检测框总数": total_boxes,
        "涉及类别": "、".join(row["中文名称"] for row in class_rows) if class_rows else "无",
        "平均置信度": round(sum(confidences) / len(confidences), 4) if confidences else 0,
        "最高置信度": round(max(confidences), 4) if confidences else 0,
        "类别统计": class_rows,
        "重点关注图片": focus_rows[:10],
        "失败图片": errors,
        "无检测结果图片": no_detection_images,
    }
