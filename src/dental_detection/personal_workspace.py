from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path
from typing import Any

from .workspace_models import DetectionTask, PatientProfile, ReportAsset, TaskStatus, UserAccount, UserRole
from .workspace_store import RecordNotFoundError, WorkspaceStore

PERSONAL_USER_ID = "personal-owner"
PERSONAL_USERNAME = "local-owner"
PERSONAL_PATIENT_ID = "personal-self"


@dataclass(frozen=True, slots=True)
class PersonalWorkspace:
    store: WorkspaceStore
    user: UserAccount
    patient: PatientProfile

    @property
    def database_path(self) -> Path:
        return self.store.database_path


def ensure_personal_workspace(
    storage_dir: str | Path | None = None,
    *,
    profile_name: str = "本人",
) -> PersonalWorkspace:
    store = WorkspaceStore(storage_dir)
    store.initialize()
    try:
        user = store.get_user(PERSONAL_USER_ID)
    except RecordNotFoundError:
        try:
            user = store.create_user(
                PERSONAL_USERNAME,
                "本机用户",
                role=UserRole.OWNER,
                user_id=PERSONAL_USER_ID,
            )
        except sqlite3.IntegrityError:
            user = store.get_user(PERSONAL_USER_ID)
    try:
        patient = store.get_patient(user.id, PERSONAL_PATIENT_ID)
    except RecordNotFoundError:
        try:
            patient = store.create_patient(
                user.id,
                profile_name,
                patient_id=PERSONAL_PATIENT_ID,
            )
        except sqlite3.IntegrityError:
            patient = store.get_patient(user.id, PERSONAL_PATIENT_ID)
    return PersonalWorkspace(store=store, user=user, patient=patient)


def personal_patient_choices(storage_dir: str | Path | None = None) -> list[tuple[str, str]]:
    workspace = ensure_personal_workspace(storage_dir)
    return [
        (
            patient.display_name
            + (f" · {patient.external_reference}" if patient.external_reference else ""),
            patient.id,
        )
        for patient in workspace.store.list_patients(workspace.user.id)
    ]


def personal_archived_patient_choices(storage_dir: str | Path | None = None) -> list[tuple[str, str]]:
    workspace = ensure_personal_workspace(storage_dir)
    return [
        (
            patient.display_name
            + (f" · {patient.external_reference}" if patient.external_reference else ""),
            patient.id,
        )
        for patient in workspace.store.list_patients(workspace.user.id, include_archived=True)
        if patient.is_archived
    ]


def get_personal_patient(
    storage_dir: str | Path | None,
    patient_id: str,
) -> PatientProfile:
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.get_patient(workspace.user.id, patient_id)


def create_personal_patient(
    storage_dir: str | Path | None,
    display_name: str,
    *,
    external_reference: str = "",
    notes: str = "",
) -> PatientProfile:
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.create_patient(
        workspace.user.id,
        display_name,
        external_reference=external_reference,
        notes=notes,
    )


def update_personal_patient(
    storage_dir: str | Path | None,
    patient_id: str,
    *,
    display_name: str,
    external_reference: str = "",
) -> PatientProfile:
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.update_patient(
        workspace.user.id,
        patient_id,
        display_name=display_name,
        external_reference=external_reference,
    )


def archive_personal_patient(
    storage_dir: str | Path | None,
    patient_id: str,
) -> PatientProfile:
    selected_patient_id = str(patient_id or "").strip()
    if selected_patient_id == PERSONAL_PATIENT_ID:
        raise ValueError("默认的“本人”档案不能归档。")
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.set_patient_archived(
        workspace.user.id,
        selected_patient_id,
        archived=True,
    )


def restore_personal_patient(
    storage_dir: str | Path | None,
    patient_id: str,
) -> PatientProfile:
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.set_patient_archived(
        workspace.user.id,
        patient_id,
        archived=False,
    )


def record_completed_detection(
    storage_dir: str | Path | None,
    patient_id: str | None,
    model_name: str,
    *,
    parameters: dict[str, Any],
    result_summary: dict[str, Any],
) -> DetectionTask:
    workspace = ensure_personal_workspace(storage_dir)
    selected_patient_id = str(patient_id or workspace.patient.id).strip()
    workspace.store.get_patient(workspace.user.id, selected_patient_id)
    task = workspace.store.create_detection_task(
        workspace.user.id,
        selected_patient_id,
        model_name,
        parameters=parameters,
    )
    workspace.store.update_task_status(workspace.user.id, task.id, TaskStatus.RUNNING)
    return workspace.store.update_task_status(
        workspace.user.id,
        task.id,
        TaskStatus.SUCCEEDED,
        result_summary=result_summary,
    )


def register_personal_report(
    storage_dir: str | Path | None,
    patient_id: str,
    task_id: str,
    report_path: str | Path,
    *,
    report_format: str,
    model_version: str = "",
) -> ReportAsset:
    workspace = ensure_personal_workspace(storage_dir)
    selected_patient_id = str(patient_id or "").strip()
    selected_task_id = str(task_id or "").strip()
    workspace.store.get_patient(workspace.user.id, selected_patient_id)
    task = workspace.store.get_detection_task(workspace.user.id, selected_task_id)
    if task.patient_id != selected_patient_id:
        raise RecordNotFoundError("检测任务不属于该患者档案。")
    path = Path(report_path).expanduser().resolve()
    try:
        storage_key = path.relative_to(workspace.store.root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("报告文件必须位于当前患者数据目录中。") from exc
    if not path.is_file():
        raise FileNotFoundError(f"报告文件不存在：{path.name}")
    return workspace.store.register_report(
        workspace.user.id,
        selected_patient_id,
        selected_task_id,
        file_name=path.name,
        report_format=report_format,
        storage_key=storage_key,
        model_version=model_version,
    )


def list_personal_reports(
    storage_dir: str | Path | None,
    patient_id: str,
    *,
    limit: int = 100,
) -> list[ReportAsset]:
    workspace = ensure_personal_workspace(storage_dir)
    return workspace.store.list_report_assets(
        workspace.user.id,
        patient_id=patient_id,
        limit=limit,
    )


def get_personal_report(
    storage_dir: str | Path | None,
    patient_id: str,
    report_id: str,
) -> ReportAsset:
    workspace = ensure_personal_workspace(storage_dir)
    report = workspace.store.get_report_asset(workspace.user.id, report_id)
    if report.patient_id != str(patient_id or "").strip():
        raise RecordNotFoundError("报告记录不属于该患者档案。")
    return report


def delete_personal_report(
    storage_dir: str | Path | None,
    patient_id: str,
    report_id: str,
) -> ReportAsset:
    workspace = ensure_personal_workspace(storage_dir)
    report = get_personal_report(storage_dir, patient_id, report_id)
    return workspace.store.delete_report_asset(workspace.user.id, report.id)
