from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UserRole(str, Enum):
    OWNER = "owner"
    DENTIST = "dentist"
    ASSISTANT = "assistant"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: str
    username: str
    display_name: str
    role: UserRole
    created_at: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class PatientProfile:
    id: str
    owner_user_id: str
    display_name: str
    external_reference: str
    notes: str
    created_at: str
    updated_at: str
    is_archived: bool = False


@dataclass(frozen=True, slots=True)
class DetectionTask:
    id: str
    owner_user_id: str
    patient_id: str
    status: TaskStatus
    model_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True, slots=True)
class ImageAsset:
    id: str
    owner_user_id: str
    patient_id: str
    task_id: str
    original_name: str
    storage_key: str
    mime_type: str
    sha256: str
    byte_size: int
    width: int | None
    height: int | None
    metadata_scrubbed: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class ReportAsset:
    id: str
    owner_user_id: str
    patient_id: str
    task_id: str
    file_name: str
    report_format: str
    storage_key: str
    model_version: str
    created_at: str
