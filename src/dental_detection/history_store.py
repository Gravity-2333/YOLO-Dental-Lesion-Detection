from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .settings_store import ensure_app_dirs, storage_root
from .result_levels import enrich_detection_row, get_confidence_level, has_detection_payload, iter_detection_items, parse_confidence
from .result_items import item_model_results, iter_model_result_items, model_result_detections, model_result_name, model_result_path
from .text_utils import json_safe_value, text_value

HISTORY_FILE_NAME = "检测历史.jsonl"
HISTORY_TABLE_COLUMNS = ["检测时间", "图片名称", "检测数量", "涉及类别", "最高置信度", "关注等级", "模型", "记录ID"]


def history_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "history"


def history_file(storage_dir: str | None = None) -> Path:
    return history_dir(storage_dir) / HISTORY_FILE_NAME


def ensure_history_dir(storage_dir: str | None = None) -> Path:
    ensure_app_dirs(storage_dir)
    target = history_dir(storage_dir)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _clean_rows(detections: Any) -> list[dict[str, Any]]:
    rows = []
    for det in iter_detection_items(detections):
        if not has_detection_payload(det):
            continue
        row = enrich_detection_row(det)
        model_name = det.get("model") or det.get("模型")
        if model_name:
            row["模型"] = text_value(model_name)
        rows.append(row)
    return rows


def _item_model_results(item: dict[str, Any]) -> list[dict[str, Any]]:
    return item_model_results(item)


def _history_model_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in _item_model_results(item):
        model_name = text_value(model_result_name(result), "unknown")
        detections = []
        for det in iter_detection_items(model_result_detections(result)):
            if not has_detection_payload(det):
                continue
            enriched = enrich_detection_row(det)
            enriched["模型"] = model_name
            detections.append(enriched)
        rows.append(
            {
                "model": model_name,
                "model_path": text_value(model_result_path(result)),
                "detection_count": len(detections),
                "detections": detections,
            }
        )
    return rows


def _model_name(item: dict[str, Any], result: dict[str, Any], summary: dict[str, Any]) -> str:
    model = result.get("model")
    if model:
        return str(model)
    model_results = summary.get("模型结果")
    for item in iter_model_result_items(model_results):
        if item.get("模型"):
            return str(item["模型"])
    return str(summary.get("模型", "unknown"))


def _record_match_key(item: dict[str, Any]) -> str:
    task_id = str(item.get("task_id") or "").strip()
    if task_id:
        return f"task:{task_id}"
    return str(item.get("display_name") or item.get("image_name") or "").strip()


def _source_match_key(source: Any) -> str:
    if isinstance(source, dict):
        task_id = str(source.get("task_id") or "").strip()
        if task_id:
            return f"task:{task_id}"
        return str(source.get("display_name") or source.get("name") or source.get("image_name") or "").strip()
    return str(source or "").strip()


def build_history_record(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("result") or item
    result = result if isinstance(result, dict) else {}
    summary = item.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    model_results = _history_model_rows(item)
    if model_results:
        rows = [row for model in model_results for row in iter_detection_items(model.get("detections"))]
        model_names = [row["model"] for row in model_results if row.get("model")]
    else:
        rows = _clean_rows(result.get("detections", []))
        model_names = [_model_name(item, result, summary)]
    confidences = [parse_confidence(row.get("confidence")) for row in rows]
    confidence_values = [value for value in confidences if value is not None]
    max_confidence = max(confidence_values) if confidence_values else None
    classes = sorted({row.get("中文名称") or row.get("class") or "未知类别" for row in rows})
    return {
        "id": uuid4().hex,
        "patient_id": item.get("patient_id") or "personal-self",
        "task_id": item.get("task_id") or "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "image_name": item.get("name") or item.get("image_name") or "未命名图片",
        "display_name": item.get("display_name") or item.get("name") or item.get("image_name") or "未命名图片",
        "detection_count": len(rows),
        "classes": classes,
        "max_confidence": round(max_confidence, 4) if max_confidence is not None else "",
        "level": get_confidence_level(max_confidence) if max_confidence is not None else "无检测结果",
        "model": "、".join(dict.fromkeys(model_names)) if model_names else _model_name(item, result, summary),
        "use_clahe": bool(summary.get("CLAHE增强", False)),
        "report_path": str(item.get("report_path") or item.get("word_report_path") or item.get("zip_report_path") or ""),
        "model_results": model_results,
        "detections": rows,
        "quality_level": item.get("quality_level", ""),
        "quality_text": item.get("quality_text", ""),
        "advice": item.get("advice", ""),
    }


def _load_raw_records(storage_dir: str | None = None) -> list[dict[str, Any]]:
    path = history_file(storage_dir)
    if not path.exists():
        return []
    records = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _write_records(records: list[dict[str, Any]], storage_dir: str | None = None) -> Path:
    ensure_history_dir(storage_dir)
    path = history_file(storage_dir)
    content = "\n".join(json.dumps(json_safe_value(item), ensure_ascii=False, allow_nan=False) for item in records)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(f"{content}\n" if content else "", encoding="utf-8")
    tmp_path.replace(path)
    return path


def append_history_records(
    batch_state: list[dict[str, Any]],
    storage_dir: str | None = None,
    limit: int = 100,
) -> Path:
    if not batch_state:
        return _write_records(_load_raw_records(storage_dir), storage_dir)
    records = _load_raw_records(storage_dir)
    records.extend(build_history_record(item) for item in batch_state)
    try:
        keep = max(1, int(limit or 100))
    except (TypeError, ValueError):
        keep = 100
    if len(records) > keep:
        records = records[-keep:]
    return _write_records(records, storage_dir)


def list_history_records(
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> list[dict[str, Any]]:
    records = _load_raw_records(storage_dir)
    selected_patient = str(patient_id or "").strip()
    if selected_patient:
        records = [
            item
            for item in records
            if str(item.get("patient_id") or "personal-self") == selected_patient
        ]
    return list(reversed(records))


def _classes_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip() or "无"
    if isinstance(value, (list, tuple, set)):
        classes = [text_value(item).strip() for item in value if text_value(item).strip()]
        return "、".join(classes) if classes else "无"
    return "无"


def history_rows(storage_dir: str | None = None, patient_id: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for item in list_history_records(storage_dir, patient_id):
        display_name = text_value(item.get("display_name") or item.get("image_name"))
        rows.append(
            {
                "检测时间": text_value(item.get("created_at")),
                "图片名称": display_name,
                "检测数量": text_value(item.get("detection_count"), "0"),
                "涉及类别": _classes_text(item.get("classes")),
                "最高置信度": text_value(item.get("max_confidence")),
                "关注等级": text_value(item.get("level")),
                "模型": text_value(item.get("model")),
                "记录ID": text_value(item.get("id")),
            }
        )
    return rows


def load_history_record(
    record_id: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> dict[str, Any] | None:
    wanted = str(record_id or "").strip()
    if not wanted:
        return None
    for item in _load_raw_records(storage_dir):
        matches_patient = not patient_id or str(item.get("patient_id") or "personal-self") == str(patient_id)
        if matches_patient and text_value(item.get("id")).strip() == wanted:
            return item
    return None


def delete_history_record(
    record_id: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> bool:
    wanted = str(record_id or "").strip()
    records = _load_raw_records(storage_dir)
    kept = [
        item
        for item in records
        if not (
            text_value(item.get("id")).strip() == wanted
            and (not patient_id or str(item.get("patient_id") or "personal-self") == str(patient_id))
        )
    ]
    if len(kept) == len(records):
        return False
    _write_records(kept, storage_dir)
    return True


def clear_history_records(storage_dir: str | None = None, patient_id: str | None = None) -> Path:
    if not patient_id:
        return _write_records([], storage_dir)
    kept = [
        item
        for item in _load_raw_records(storage_dir)
        if str(item.get("patient_id") or "personal-self") != str(patient_id)
    ]
    return _write_records(kept, storage_dir)


def update_history_report_paths(
    image_names: list[Any],
    report_path: str | Path,
    storage_dir: str | None = None,
) -> int:
    names = [_source_match_key(name) for name in image_names if _source_match_key(name)]
    if not names:
        return 0
    records = _load_raw_records(storage_dir)
    changed = 0
    remaining = Counter(names)
    path_text = str(report_path)
    for item in reversed(records):
        match_key = _record_match_key(item)
        if remaining.get(match_key, 0) > 0:
            item["report_path"] = path_text
            remaining[match_key] -= 1
            changed += 1
        if not any(remaining.values()):
            break
    if changed:
        _write_records(records, storage_dir)
    return changed
