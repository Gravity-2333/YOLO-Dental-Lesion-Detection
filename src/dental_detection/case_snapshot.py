from __future__ import annotations

import base64
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from PIL import Image

from .personal_workspace import PERSONAL_PATIENT_ID, PERSONAL_USER_ID, ensure_personal_workspace
from .image_quality import assess_image_quality_detail
from .text_utils import json_safe_value
from .settings_store import case_dir
from .visualization import as_rgb_image
from .workspace_store import WorkspaceError, normalize_storage_key

CASE_FORMAT_VERSION = 2
LEGACY_CASE_MESSAGE = "该旧病例未保存影像，无法完整恢复"


def _png_bytes(image: Any) -> tuple[bytes, tuple[int, int]]:
    if image is None:
        raise ValueError("当前检测缺少影像，请重新检测后再保存病例。")
    source = as_rgb_image(image)
    # Rebuild from pixels so patient-identifying EXIF/text metadata is not persisted.
    clean = Image.frombytes("RGB", source.size, source.tobytes())
    output = io.BytesIO()
    clean.save(output, format="PNG")
    return output.getvalue(), clean.size


def _private_path(root: Path, storage_key: str) -> Path:
    path = (root / normalize_storage_key(storage_key)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("病例资产路径超出当前数据目录。")
    return path


def _reports_for_snapshot(item: dict[str, Any], root: Path) -> dict[str, Any]:
    reports = {}
    for field in ("report_path", "word_report_path", "zip_report_path"):
        value = str(item.get(field) or "").strip()
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        reports[field] = {
            "storage_key": path.relative_to(root).as_posix(),
            "file_name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return reports


def save_case_snapshot(
    storage_dir: str,
    file_name: str,
    payload: dict[str, Any],
    item: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    if not results:
        raise ValueError("当前没有可保存的模型结果。")
    if Path(file_name).name != file_name or not file_name.startswith("case_") or not file_name.endswith(".json"):
        raise ValueError("病例文件名无效。")
    workspace = ensure_personal_workspace(storage_dir)
    root = workspace.store.root.resolve()
    patient_id = str(payload.get("patient_id") or PERSONAL_PATIENT_ID)
    task = workspace.store.get_detection_task(workspace.user.id, str(payload.get("task_id") or ""))
    if task.patient_id != patient_id:
        raise ValueError("检测任务不属于当前患者档案。")
    snapshot_id = uuid4().hex
    assets_parent = _private_path(root, "cases/assets")
    assets_parent.mkdir(parents=True, exist_ok=True)
    staging = assets_parent / f".pending-{snapshot_id}"
    destination = assets_parent / snapshot_id
    manifest = case_dir(storage_dir) / file_name
    pending_manifest = manifest.with_suffix(f".{snapshot_id}.pending")
    if manifest.exists():
        raise FileExistsError("病例文件已存在，请刷新后重试。")
    staging.mkdir()
    images = []
    assets: dict[str, Any] = {}
    by_digest: dict[str, str] = {}

    def add_image(role: str, image: Any, key: str) -> str:
        content, size = _png_bytes(image)
        digest = hashlib.sha256(content).hexdigest()
        if digest in by_digest:
            assets[key] = {"role": role, "reuse_of": by_digest[digest]}
            return key
        image_id = uuid4().hex
        name = f"{key}.png"
        (staging / name).write_bytes(content)
        metadata = dict(
            image_id=image_id, original_name=name,
            storage_key=f"cases/assets/{snapshot_id}/{name}", mime_type="image/png",
            sha256=digest, byte_size=len(content), width=size[0], height=size[1],
            metadata_scrubbed=True, asset_role=role,
        )
        images.append(metadata)
        assets[key] = {"role": role, "image_id": image_id}
        by_digest[digest] = key
        return key

    published = False
    try:
        original = add_image("original", results[0].get("original"), "original")
        model_input = add_image("model_input", results[0].get("model_input"), "model_input")
        model_records = []
        for index, result in enumerate(results):
            annotated = result.get("full_annotated")
            if annotated is None:
                annotated = result.get("annotated")
            annotation_key = add_image("annotated", annotated, f"annotated_{index}")
            saved_result = payload["model_results"][index]
            weight_path = Path(str(saved_result.get("model_path") or ""))
            weight_digest = hashlib.sha256(weight_path.read_bytes()).hexdigest() if weight_path.is_file() else ""
            raw = saved_result.get("detections", [])
            model_records.append({
                **saved_result,
                "weights_sha256": weight_digest,
                "class_names": result.get("class_names", {}),
                "original_asset": original, "model_input_asset": model_input,
                "annotated_asset": annotation_key,
                "raw_detections": result.get("raw_detections", raw),
                "reviewed_detections": result.get("reviewed_detections", raw),
                "review_status": result.get("review_status", "unreviewed"),
            })
        snapshot = json_safe_value({
            **payload, "case_format_version": CASE_FORMAT_VERSION,
            "snapshot_id": snapshot_id, "owner_user_id": workspace.user.id,
            "patient_id": patient_id, "parameters": {"imgsz": 1280, **task.parameters},
            "quality_metrics": asdict(assess_image_quality_detail(results[0]["original"])),
            "model_results": model_records, "image_assets": assets,
            "reports": _reports_for_snapshot(item, root),
            "report_asset_ids": item.get("report_asset_ids", {}),
        })
        # Legacy report path fields remain present, but never retain the old root.
        for field in ("report_path", "word_report_path", "zip_report_path"):
            snapshot[field] = snapshot["reports"].get(field, {}).get("storage_key", "")
        with workspace.store.image_asset_transaction(workspace.user.id, patient_id, task.id, images) as records:
            for record in records:
                asset = next(value for value in assets.values() if value.get("image_id") == record.id)
                asset.update(asdict(record))
            snapshot["image_assets"] = assets
            pending_manifest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            staging.rename(destination)
            pending_manifest.rename(manifest)
            published = True
        return snapshot
    except BaseException:
        if published:
            manifest.unlink(missing_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        raise
    finally:
        pending_manifest.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging)


def load_case_snapshot(storage_dir: str, data: dict[str, Any], patient_id: str | None = None) -> dict[str, Any]:
    version = data.get("case_format_version", 1)
    if version == 1:
        raise ValueError(LEGACY_CASE_MESSAGE)
    if version != CASE_FORMAT_VERSION:
        raise ValueError("该病例格式版本暂不支持，请升级应用后再打开。")
    workspace = ensure_personal_workspace(storage_dir)
    selected_patient = str(patient_id or PERSONAL_PATIENT_ID)
    if data.get("patient_id") != selected_patient or data.get("owner_user_id") != PERSONAL_USER_ID:
        raise ValueError("该病例不属于当前患者档案。")
    task = workspace.store.get_detection_task(workspace.user.id, str(data.get("task_id") or ""))
    if task.patient_id != selected_patient:
        raise ValueError("病例检测任务与患者档案不匹配。")
    assets = data.get("image_assets")
    models = data.get("model_results")
    if not isinstance(assets, dict) or not isinstance(models, list) or not models or len(models) > 2:
        raise ValueError("病例缺少完整影像或模型结果。")
    cache: dict[str, tuple[Image.Image, bytes]] = {}

    def image_for(key: str, role: str) -> tuple[Image.Image, bytes]:
        visited = set()
        asset = assets.get(key)
        if not isinstance(asset, dict) or asset.get("role") != role:
            raise ValueError("病例影像角色不匹配。")
        while asset.get("reuse_of"):
            if key in visited:
                raise ValueError("病例影像复用关系存在循环。")
            visited.add(key)
            key = str(asset["reuse_of"])
            asset = assets.get(key)
            if not isinstance(asset, dict):
                raise ValueError("病例影像复用关系无效。")
        if key in cache:
            return cache[key]
        record = workspace.store.get_image_asset(workspace.user.id, str(asset.get("image_id") or ""))
        if record.patient_id != selected_patient or record.task_id != task.id:
            raise ValueError("病例影像不属于当前患者或检测任务。")
        if asset.get("role") != record.asset_role:
            raise ValueError("病例影像角色与数据库登记不一致。")
        for field in ("storage_key", "sha256", "byte_size", "width", "height", "asset_role"):
            if asset.get(field) != getattr(record, field):
                raise ValueError("病例影像登记信息不一致。")
        path = _private_path(workspace.store.root, record.storage_key)
        if not path.is_file():
            raise FileNotFoundError("病例影像文件缺失，请从备份恢复后重试。")
        content = path.read_bytes()
        if len(content) != record.byte_size or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("病例影像完整性校验失败，文件可能已损坏。")
        with Image.open(io.BytesIO(content)) as image:
            if image.size != (record.width, record.height) or image.format != "PNG":
                raise ValueError("病例影像尺寸或格式校验失败。")
            decoded = image.convert("RGB")
        cache[key] = decoded, content
        return cache[key]

    results = []
    previews = []
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("detections"), list):
            raise ValueError("病例检测结果格式无效。")
        original, original_bytes = image_for(str(model.get("original_asset") or ""), "original")
        model_input, input_bytes = image_for(str(model.get("model_input_asset") or ""), "model_input")
        annotated, annotated_bytes = image_for(str(model.get("annotated_asset") or ""), "annotated")
        results.append({**model, "original": original, "model_input": model_input,
                        "annotated": annotated, "full_annotated": annotated})
        previews.append({"model": model.get("model"), "size": original.size,
                         "annotated": "data:image/png;base64," + base64.b64encode(annotated_bytes).decode("ascii")})
    reports = {}
    for field, report in (data.get("reports") or {}).items():
        if field not in {"report_path", "word_report_path", "zip_report_path"} or not isinstance(report, dict):
            continue
        path = _private_path(workspace.store.root, str(report.get("storage_key") or ""))
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == report.get("sha256"):
            reports[field] = str(path)
    return {
        "name": data.get("image_name") or "当前单图",
        "display_name": data.get("display_name") or data.get("image_name") or "当前单图",
        "patient_id": selected_patient, "task_id": task.id,
        "result": results[0], "all_results": results,
        "summary": data.get("summary", {}), "parameters": data.get("parameters", task.parameters),
        "advice": data.get("suggestion", ""), "suggestion_type": data.get("suggestion_type", ""),
        "quality_text": data.get("quality_text", ""), "quality_level": data.get("quality_level", ""),
        "report_asset_ids": data.get("report_asset_ids", {}), **reports,
        "_previews": previews,
        "_source_previews": {
            "original": "data:image/png;base64," + base64.b64encode(original_bytes).decode("ascii"),
            "model_input": "data:image/png;base64," + base64.b64encode(input_bytes).decode("ascii"),
        },
    }


def case_snapshot_detail_data(storage_dir: str, data: dict[str, Any]) -> dict[str, Any]:
    if data.get("case_format_version", 1) == 1:
        return data
    try:
        item = load_case_snapshot(storage_dir, data, data.get("patient_id"))
        return {**data, "_previews": item["_previews"], "_source_previews": item["_source_previews"]}
    except (OSError, WorkspaceError, ValueError, TypeError, KeyError) as exc:
        return {**data, "_snapshot_error": str(exc)}


def reusable_case_snapshot(
    storage_dir: str,
    existing: dict[str, Any],
    payload: dict[str, Any],
    item: dict[str, Any],
) -> bool:
    if existing.get("case_format_version") != CASE_FORMAT_VERSION:
        return False
    fields = ("summary", "quality_text", "quality_level", "suggestion", "suggestion_type")
    if any(existing.get(field) != json_safe_value(payload.get(field)) for field in fields):
        return False
    model_fields = ("model", "model_path", "detections")
    saved_results = existing.get("model_results")
    current_results = payload.get("model_results")
    for models in (saved_results, current_results):
        if not isinstance(models, list) or not models or not all(isinstance(model, dict) for model in models):
            return False
    saved_models = [{key: model.get(key) for key in model_fields} for model in saved_results]
    current_models = [{key: model.get(key) for key in model_fields} for model in current_results]
    if saved_models != json_safe_value(current_models):
        return False
    root = ensure_personal_workspace(storage_dir).store.root.resolve()
    if existing.get("reports", {}) != _reports_for_snapshot(item, root):
        return False
    detail = case_snapshot_detail_data(storage_dir, existing)
    return bool(detail.get("_previews")) and not detail.get("_snapshot_error")
