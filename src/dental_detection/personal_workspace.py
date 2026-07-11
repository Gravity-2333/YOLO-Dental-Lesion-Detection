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
