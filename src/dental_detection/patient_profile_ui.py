from __future__ import annotations

import sqlite3

import gradio as gr

from .error_messages import friendly_error_message
from .personal_workspace import (
    PERSONAL_PATIENT_ID,
    archive_personal_patient,
    create_personal_patient,
    ensure_personal_workspace,
    get_personal_patient,
    personal_archived_patient_choices,
    personal_patient_choices,
    restore_personal_patient,
    update_personal_patient,
)
from .ui_content import toast_html
from .workspace_store import WorkspaceError


def _gr_error(exc: BaseException, context: str) -> gr.Error:
    return gr.Error(friendly_error_message(exc, context))


def sync_patient_selections(patient_id: str | None):
    value = str(patient_id or "").strip() or None
    return gr.update(value=value), gr.update(value=value)


def refresh_patient_selection_choices(storage_dir: str, patient_id: str | None):
    try:
        choices = personal_patient_choices(storage_dir)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案列表读取失败") from exc
    values = {value for _, value in choices}
    selected = str(patient_id or "").strip()
    if selected not in values:
        selected = (
            PERSONAL_PATIENT_ID
            if PERSONAL_PATIENT_ID in values
            else (choices[0][1] if choices else None)
        )
    return tuple(gr.update(choices=choices, value=selected) for _ in range(3))


def add_patient_profile(display_name: str, external_reference: str, storage_dir: str):
    name = str(display_name or "").strip()
    if not name:
        raise gr.Error("请输入患者档案名称。")
    try:
        patient = create_personal_patient(
            storage_dir,
            name,
            external_reference=str(external_reference or "").strip(),
        )
        choices = personal_patient_choices(storage_dir)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案创建失败") from exc
    return (
        gr.update(choices=choices, value=patient.id),
        gr.update(choices=choices, value=patient.id),
        gr.update(choices=choices, value=patient.id),
        "",
        "",
        toast_html(f"已创建患者档案：{patient.display_name}"),
        patient.id,
    )


def load_patient_profile_form(patient_id: str, storage_dir: str):
    try:
        patient = get_personal_patient(storage_dir, patient_id)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案读取失败") from exc
    return (
        patient.display_name,
        patient.external_reference,
        gr.update(interactive=patient.id != PERSONAL_PATIENT_ID),
    )


def update_patient_profile(
    patient_id: str,
    display_name: str,
    external_reference: str,
    storage_dir: str,
):
    name = str(display_name or "").strip()
    if not name:
        raise gr.Error("患者档案名称不能为空。")
    try:
        patient = update_personal_patient(
            storage_dir,
            patient_id,
            display_name=name,
            external_reference=str(external_reference or "").strip(),
        )
        choices = personal_patient_choices(storage_dir)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案更新失败") from exc
    selection_updates = [gr.update(choices=choices, value=patient.id) for _ in range(3)]
    return (
        *selection_updates,
        patient.display_name,
        patient.external_reference,
        gr.update(interactive=patient.id != PERSONAL_PATIENT_ID),
        toast_html(f"患者档案已更新：{patient.display_name}"),
        patient.id,
    )


def archive_patient_profile(patient_id: str, storage_dir: str):
    try:
        archived = archive_personal_patient(storage_dir, patient_id)
        workspace = ensure_personal_workspace(storage_dir)
        active_choices = personal_patient_choices(storage_dir)
        archived_choices = personal_archived_patient_choices(storage_dir)
        fallback = workspace.patient
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案归档失败") from exc
    selection_updates = [gr.update(choices=active_choices, value=fallback.id) for _ in range(3)]
    return (
        *selection_updates,
        gr.update(choices=archived_choices, value=archived.id),
        fallback.display_name,
        fallback.external_reference,
        gr.update(interactive=False),
        gr.update(interactive=bool(archived_choices)),
        toast_html(f"患者档案已归档：{archived.display_name}"),
        fallback.id,
    )


def restore_patient_profile(patient_id: str, storage_dir: str):
    if not str(patient_id or "").strip():
        raise gr.Error("请选择要恢复的患者档案。")
    try:
        restored = restore_personal_patient(storage_dir, patient_id)
        active_choices = personal_patient_choices(storage_dir)
        archived_choices = personal_archived_patient_choices(storage_dir)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise _gr_error(exc, "患者档案恢复失败") from exc
    selection_updates = [gr.update(choices=active_choices, value=restored.id) for _ in range(3)]
    archived_value = archived_choices[0][1] if archived_choices else None
    return (
        *selection_updates,
        gr.update(choices=archived_choices, value=archived_value),
        restored.display_name,
        restored.external_reference,
        gr.update(interactive=True),
        gr.update(interactive=bool(archived_choices)),
        toast_html(f"患者档案已恢复：{restored.display_name}"),
        restored.id,
    )
