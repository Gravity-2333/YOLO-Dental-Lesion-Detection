from __future__ import annotations

from typing import Any


_DETECTION_KEYS = {
    "class",
    "类别",
    "label",
    "name",
    "confidence",
    "置信度",
    "x1",
    "y1",
    "x2",
    "y2",
}


def _result_has_detections(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    for det in result.get("detections") or []:
        if isinstance(det, dict) and any(key in det for key in _DETECTION_KEYS):
            return True
    return False


def _result_has_artifacts(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    artifact_keys = (
        "original",
        "original_image",
        "model_input",
        "input_image",
        "annotated",
        "full_annotated",
        "result_image",
    )
    return any(
        result.get(key) is not None
        for key in artifact_keys
    )


def item_model_results(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Return model results without letting empty stale details hide primary detections."""
    results = item.get("all_results")
    primary = item.get("result") or item
    primary = primary if isinstance(primary, dict) else {}
    if isinstance(results, list) and results:
        model_results = [result for result in results if isinstance(result, dict)]
        if model_results:
            if any(_result_has_detections(result) for result in model_results):
                return model_results
            if _result_has_detections(primary):
                return [primary]
            if any(_result_has_artifacts(result) for result in model_results):
                return model_results
            if _result_has_artifacts(primary):
                return [primary]
            return model_results
    return [primary] if primary else []
