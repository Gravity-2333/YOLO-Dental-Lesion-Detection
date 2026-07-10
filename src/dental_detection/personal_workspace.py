from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path

from .workspace_models import PatientProfile, UserAccount, UserRole
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
