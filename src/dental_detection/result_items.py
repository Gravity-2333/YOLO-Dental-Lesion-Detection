from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .result_levels import has_detection_payload, iter_detection_items


def model_result_name(result: dict[str, Any], fallback: str = "unknown") -> str:
    return str(result.get("model") or result.get("模型") or fallback)


def model_result_path(result: dict[str, Any]) -> str:
    return str(result.get("model_path") or result.get("路径") or result.get("模型路径") or "")


def model_result_detections(result: dict[str, Any]) -> Any:
    if "detections" in result:
        return result.get("detections")
    return result.get("检测框")


def iter_model_result_items(results: Any):
    if isinstance(results, dict):
        candidates = (results,)
    elif isinstance(results, Iterable) and not isinstance(results, (str, bytes, bytearray)):
        candidates = results
    else:
        candidates = ()
    for item in candidates:
        if isinstance(item, dict):
            yield item


def _result_has_detections(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    for det in iter_detection_items(model_result_detections(result)):
        if has_detection_payload(det):
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
    results = list(iter_model_result_items(item.get("all_results")))
    primary = item.get("result") or item
    primary = primary if isinstance(primary, dict) else {}
    if results:
        if any(_result_has_detections(result) for result in results):
            return results
        if _result_has_detections(primary):
            return [primary]
        if any(_result_has_artifacts(result) for result in results):
            return results
        if _result_has_artifacts(primary):
            return [primary]
        return results
    return [primary] if primary else []
