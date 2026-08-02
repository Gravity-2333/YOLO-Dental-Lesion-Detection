from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .result_items import item_model_results, model_result_detections, model_result_name
from .result_levels import enrich_detection_row, has_detection_payload, iter_detection_items
from .text_utils import json_safe_value


@dataclass(frozen=True, slots=True)
class DetectionTextContext:
    available: bool
    detection_count: int
    model_count: int
    prompt_text: str


def _matches_selected_item(item: dict[str, Any], selected_name: Any) -> bool:
    selected_text = str(selected_name or "").strip()
    if not selected_text:
        return False
    return any(
        str(item.get(field) or "").strip() == selected_text
        for field in ("display_name", "name", "image_name")
    )


def _selected_item(batch_state: Any, selected_name: Any) -> dict[str, Any] | None:
    items = [item for item in (batch_state or []) if isinstance(item, dict)]
    if not items:
        return None
    if str(selected_name or "").strip():
        return next(
            (item for item in items if _matches_selected_item(item, selected_name)),
            None,
        )
    return items[0]


def build_detection_text_context(
    batch_state: Any,
    selected_name: Any = None,
) -> DetectionTextContext:
    """Build the only detection payload allowed to reach the external AI service."""
    item = _selected_item(batch_state, selected_name)
    if item is None:
        return DetectionTextContext(
            available=False,
            detection_count=0,
            model_count=0,
            prompt_text="当前没有活动检测结果。不要臆造检测类别、数量、置信度或位置。",
        )

    model_summaries: list[dict[str, Any]] = []
    detection_count = 0
    for result in item_model_results(item):
        rows: list[dict[str, Any]] = []
        for raw_row in iter_detection_items(model_result_detections(result)):
            if not has_detection_payload(raw_row):
                continue
            row = enrich_detection_row(raw_row)
            rows.append(
                {
                    "类别": row["中文名称"],
                    "置信度": row["confidence"],
                    "关注等级": row["关注等级"],
                    "图像区域": row["图像区域"],
                    "检测框": [row["x1"], row["y1"], row["x2"], row["y2"]],
                }
            )
        detection_count += len(rows)
        model_summaries.append(
            {
                "模型": model_result_name(result),
                "检测数量": len(rows),
                "检测框": rows,
            }
        )

    payload = {
        "检测已完成": True,
        "模型数量": len(model_summaries),
        "检测框总数": detection_count,
        "模型结果": model_summaries,
        "说明": "图像区域为检测框在影像中的粗略位置，不等同于专业牙位编号。",
    }
    return DetectionTextContext(
        available=True,
        detection_count=detection_count,
        model_count=len(model_summaries),
        prompt_text=json.dumps(
            json_safe_value(payload),
            ensure_ascii=False,
            allow_nan=False,
        ),
    )
