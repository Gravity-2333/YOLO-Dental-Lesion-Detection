from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .assistant import ensure_app_dirs, storage_root
from .result_levels import enrich_detection_row, get_confidence_level, parse_confidence

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
    for det in detections or []:
        if isinstance(det, dict):
            rows.append(enrich_detection_row(det))
    return rows


def _model_name(item: dict[str, Any], result: dict[str, Any], summary: dict[str, Any]) -> str:
    model = result.get("model")
    if model:
        return str(model)
    model_results = summary.get("模型结果")
    if isinstance(model_results, list) and model_results:
        first = model_results[0]
        if isinstance(first, dict) and first.get("模型"):
            return str(first["模型"])
    return str(summary.get("模型", "unknown"))


def build_history_record(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("result") or item
    result = result if isinstance(result, dict) else {}
    summary = item.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    rows = _clean_rows(result.get("detections", []))
    confidences = [parse_confidence(row.get("confidence")) for row in rows]
    confidence_values = [value for value in confidences if value is not None]
    max_confidence = max(confidence_values) if confidence_values else None
    classes = sorted({row.get("中文名称") or row.get("class") or "未知类别" for row in rows})
    return {
        "id": uuid4().hex,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "image_name": item.get("name") or item.get("image_name") or "未命名图片",
        "detection_count": len(rows),
        "classes": classes,
        "max_confidence": round(max_confidence, 4) if max_confidence is not None else "",
        "level": get_confidence_level(max_confidence) if max_confidence is not None else "无检测结果",
        "model": _model_name(item, result, summary),
        "use_clahe": bool(summary.get("CLAHE增强", False)),
        "report_path": str(item.get("word_report_path") or item.get("report_path") or ""),
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
    except OSError:
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
    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in records)
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")
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


def list_history_records(storage_dir: str | None = None) -> list[dict[str, Any]]:
    return list(reversed(_load_raw_records(storage_dir)))


def _classes_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip() or "无"
    if isinstance(value, (list, tuple, set)):
        classes = [str(item).strip() for item in value if str(item).strip()]
        return "、".join(classes) if classes else "无"
    return "无"


def history_rows(storage_dir: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for item in list_history_records(storage_dir):
        rows.append(
            {
                "检测时间": item.get("created_at", ""),
                "图片名称": item.get("image_name", ""),
                "检测数量": item.get("detection_count", 0),
                "涉及类别": _classes_text(item.get("classes")),
                "最高置信度": item.get("max_confidence", ""),
                "关注等级": item.get("level", ""),
                "模型": item.get("model", ""),
                "记录ID": item.get("id", ""),
            }
        )
    return rows


def load_history_record(record_id: str, storage_dir: str | None = None) -> dict[str, Any] | None:
    wanted = str(record_id or "").strip()
    if not wanted:
        return None
    for item in _load_raw_records(storage_dir):
        if item.get("id") == wanted:
            return item
    return None


def delete_history_record(record_id: str, storage_dir: str | None = None) -> bool:
    wanted = str(record_id or "").strip()
    records = _load_raw_records(storage_dir)
    kept = [item for item in records if item.get("id") != wanted]
    if len(kept) == len(records):
        return False
    _write_records(kept, storage_dir)
    return True


def clear_history_records(storage_dir: str | None = None) -> Path:
    return _write_records([], storage_dir)


def update_history_report_paths(
    image_names: list[str],
    report_path: str | Path,
    storage_dir: str | None = None,
) -> int:
    names = [str(name or "").strip() for name in image_names if str(name or "").strip()]
    if not names:
        return 0
    records = _load_raw_records(storage_dir)
    changed = 0
    remaining = Counter(names)
    path_text = str(report_path)
    for item in reversed(records):
        image_name = str(item.get("image_name") or "").strip()
        if remaining.get(image_name, 0) > 0:
            item["report_path"] = path_text
            remaining[image_name] -= 1
            changed += 1
        if not any(remaining.values()):
            break
    if changed:
        _write_records(records, storage_dir)
    return changed
