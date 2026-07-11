from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Any
from uuid import uuid4

from .settings_store import ensure_app_dirs, storage_root
from .workspace_models import (
    DetectionTask,
    ImageAsset,
    PatientProfile,
    ReportAsset,
    TaskStatus,
    UserAccount,
    UserRole,
)

SCHEMA_VERSION = 1
WORKSPACE_DIR_NAME = "workspace"
WORKSPACE_DATABASE_NAME = "workspace.sqlite3"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class WorkspaceError(RuntimeError):
    pass


class RecordNotFoundError(WorkspaceError):
    pass


class InvalidTaskTransitionError(WorkspaceError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _identifier(value: str | None, *, generate: bool = False) -> str:
    identifier = str(value or (uuid4().hex if generate else "")).strip()
    if not _ID_RE.fullmatch(identifier):
        raise ValueError("记录标识无效。")
    return identifier


def _required_text(value: Any, label: str, *, max_length: int = 255) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label}不能为空。")
    if len(text) > max_length:
        raise ValueError(f"{label}不能超过 {max_length} 个字符。")
    return text


def _optional_text(value: Any, *, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ValueError(f"文本不能超过 {max_length} 个字符。")
    return text


def _json_object(value: dict[str, Any] | None) -> str:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise TypeError("结构化字段必须是字典。")
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _load_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise WorkspaceError("工作区数据库包含损坏的结构化字段。") from exc
    if not isinstance(parsed, dict):
        raise WorkspaceError("工作区数据库中的结构化字段类型无效。")
    return parsed


def normalize_storage_key(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or ":" in text:
        raise ValueError("存储键必须是非空相对路径。")
    path = PurePosixPath(text)
    if (
        path.as_posix() in {"", "."}
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("存储键不能包含绝对路径或目录跳转。")
    return path.as_posix()


class WorkspaceStore:
    def __init__(self, storage_dir: str | Path | None = None):
        root = storage_root(str(storage_dir) if storage_dir is not None else None)
        self.root = root.expanduser()
        self.workspace_dir = self.root / WORKSPACE_DIR_NAME
        self.database_path = self.workspace_dir / WORKSPACE_DATABASE_NAME

    def initialize(self) -> Path:
        ensure_app_dirs(str(self.root))
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            if applied and max(applied) > SCHEMA_VERSION:
                raise WorkspaceError("工作区数据库版本高于当前程序支持的版本。")
            if 1 not in applied:
                self._apply_schema_v1(connection)
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, _now()),
                )
        return self.database_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _apply_schema_v1(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('owner', 'dentist', 'assistant')),
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                display_name TEXT NOT NULL,
                external_reference TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0 CHECK(is_archived IN (0, 1)),
                UNIQUE(id, owner_user_id)
            );
            CREATE INDEX IF NOT EXISTS patients_owner_idx ON patients(owner_user_id, is_archived, updated_at DESC);

            CREATE TABLE IF NOT EXISTS detection_tasks (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                patient_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
                model_name TEXT NOT NULL,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                result_summary_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                UNIQUE(id, owner_user_id),
                FOREIGN KEY(patient_id, owner_user_id) REFERENCES patients(id, owner_user_id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS detection_tasks_owner_patient_idx
                ON detection_tasks(owner_user_id, patient_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS image_assets (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                patient_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
                width INTEGER CHECK(width IS NULL OR width > 0),
                height INTEGER CHECK(height IS NULL OR height > 0),
                metadata_scrubbed INTEGER NOT NULL CHECK(metadata_scrubbed IN (0, 1)),
                created_at TEXT NOT NULL,
                UNIQUE(owner_user_id, storage_key),
                FOREIGN KEY(patient_id, owner_user_id) REFERENCES patients(id, owner_user_id) ON DELETE RESTRICT,
                FOREIGN KEY(task_id, owner_user_id) REFERENCES detection_tasks(id, owner_user_id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS image_assets_task_idx ON image_assets(owner_user_id, task_id, created_at);

            CREATE TABLE IF NOT EXISTS report_assets (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                patient_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                report_format TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(owner_user_id, storage_key),
                FOREIGN KEY(patient_id, owner_user_id) REFERENCES patients(id, owner_user_id) ON DELETE RESTRICT,
                FOREIGN KEY(task_id, owner_user_id) REFERENCES detection_tasks(id, owner_user_id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS report_assets_task_idx ON report_assets(owner_user_id, task_id, created_at);
            """
        )

    def schema_version(self) -> int:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
        return int(row[0])

    def create_user(
        self,
        username: str,
        display_name: str,
        *,
        role: UserRole = UserRole.OWNER,
        user_id: str | None = None,
    ) -> UserAccount:
        self.initialize()
        record = UserAccount(
            id=_identifier(user_id, generate=True),
            username=_required_text(username, "用户名", max_length=100),
            display_name=_required_text(display_name, "显示名称", max_length=100),
            role=UserRole(role),
            created_at=_now(),
        )
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO users(id, username, display_name, role, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (record.id, record.username, record.display_name, record.role.value, record.created_at),
            )
        return record

    def get_user(self, user_id: str) -> UserAccount:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (_identifier(user_id),)).fetchone()
        if row is None:
            raise RecordNotFoundError("用户不存在。")
        return self._user_from_row(row)

    def create_patient(
        self,
        owner_user_id: str,
        display_name: str,
        *,
        external_reference: str = "",
        notes: str = "",
        patient_id: str | None = None,
    ) -> PatientProfile:
        self.get_user(owner_user_id)
        now = _now()
        record = PatientProfile(
            id=_identifier(patient_id, generate=True),
            owner_user_id=_identifier(owner_user_id),
            display_name=_required_text(display_name, "患者档案名称", max_length=120),
            external_reference=_optional_text(external_reference, max_length=120),
            notes=_optional_text(notes, max_length=4000),
            created_at=now,
            updated_at=now,
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO patients(
                    id, owner_user_id, display_name, external_reference, notes, created_at, updated_at, is_archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    record.id,
                    record.owner_user_id,
                    record.display_name,
                    record.external_reference,
                    record.notes,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get_patient(self, owner_user_id: str, patient_id: str) -> PatientProfile:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM patients WHERE id = ? AND owner_user_id = ?",
                (_identifier(patient_id), _identifier(owner_user_id)),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError("患者档案不存在。")
        return self._patient_from_row(row)

    def list_patients(self, owner_user_id: str, *, include_archived: bool = False) -> list[PatientProfile]:
        self.get_user(owner_user_id)
        query = "SELECT * FROM patients WHERE owner_user_id = ?"
        parameters: list[Any] = [_identifier(owner_user_id)]
        if not include_archived:
            query += " AND is_archived = 0"
        query += " ORDER BY updated_at DESC, id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._patient_from_row(row) for row in rows]

    def update_patient(
        self,
        owner_user_id: str,
        patient_id: str,
        *,
        display_name: str,
        external_reference: str = "",
        notes: str | None = None,
    ) -> PatientProfile:
        current = self.get_patient(owner_user_id, patient_id)
        updated_notes = current.notes if notes is None else _optional_text(notes, max_length=4000)
        with self._connection() as connection:
            connection.execute(
                """UPDATE patients
                   SET display_name = ?, external_reference = ?, notes = ?, updated_at = ?
                   WHERE id = ? AND owner_user_id = ?""",
                (
                    _required_text(display_name, "患者档案名称", max_length=120),
                    _optional_text(external_reference, max_length=120),
                    updated_notes,
                    _now(),
                    current.id,
                    current.owner_user_id,
                ),
            )
        return self.get_patient(owner_user_id, patient_id)

    def set_patient_archived(
        self,
        owner_user_id: str,
        patient_id: str,
        *,
        archived: bool,
    ) -> PatientProfile:
        current = self.get_patient(owner_user_id, patient_id)
        with self._connection() as connection:
            connection.execute(
                """UPDATE patients SET is_archived = ?, updated_at = ?
                   WHERE id = ? AND owner_user_id = ?""",
                (int(bool(archived)), _now(), current.id, current.owner_user_id),
            )
        return self.get_patient(owner_user_id, patient_id)

    def create_detection_task(
        self,
        owner_user_id: str,
        patient_id: str,
        model_name: str,
        *,
        parameters: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> DetectionTask:
        self.get_patient(owner_user_id, patient_id)
        record = DetectionTask(
            id=_identifier(task_id, generate=True),
            owner_user_id=_identifier(owner_user_id),
            patient_id=_identifier(patient_id),
            status=TaskStatus.QUEUED,
            model_name=_required_text(model_name, "模型名称", max_length=255),
            parameters=parameters or {},
            created_at=_now(),
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO detection_tasks(
                    id, owner_user_id, patient_id, status, model_name, parameters_json,
                    result_summary_json, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, '{}', '', ?)""",
                (
                    record.id,
                    record.owner_user_id,
                    record.patient_id,
                    record.status.value,
                    record.model_name,
                    _json_object(record.parameters),
                    record.created_at,
                ),
            )
        return record

    def get_detection_task(self, owner_user_id: str, task_id: str) -> DetectionTask:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM detection_tasks WHERE id = ? AND owner_user_id = ?",
                (_identifier(task_id), _identifier(owner_user_id)),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError("检测任务不存在。")
        return self._task_from_row(row)

    def list_detection_tasks(
        self,
        owner_user_id: str,
        *,
        patient_id: str | None = None,
        limit: int = 100,
    ) -> list[DetectionTask]:
        self.get_user(owner_user_id)
        query = "SELECT * FROM detection_tasks WHERE owner_user_id = ?"
        parameters: list[Any] = [_identifier(owner_user_id)]
        if patient_id is not None:
            self.get_patient(owner_user_id, patient_id)
            query += " AND patient_id = ?"
            parameters.append(_identifier(patient_id))
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(max(1, min(1000, int(limit))))
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._task_from_row(row) for row in rows]

    def update_task_status(
        self,
        owner_user_id: str,
        task_id: str,
        status: TaskStatus,
        *,
        result_summary: dict[str, Any] | None = None,
        error_message: str = "",
    ) -> DetectionTask:
        current = self.get_detection_task(owner_user_id, task_id)
        target = TaskStatus(status)
        allowed = {
            TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED},
            TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED},
            TaskStatus.SUCCEEDED: set(),
            TaskStatus.FAILED: set(),
            TaskStatus.CANCELLED: set(),
        }
        if target not in allowed[current.status]:
            raise InvalidTaskTransitionError(f"检测任务不能从 {current.status.value} 变为 {target.value}。")
        now = _now()
        started_at = current.started_at or (now if target == TaskStatus.RUNNING else None)
        completed_at = now if target in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED} else None
        summary_json = _json_object(result_summary if result_summary is not None else current.result_summary)
        error = _optional_text(error_message, max_length=4000)
        with self._connection() as connection:
            connection.execute(
                """UPDATE detection_tasks
                   SET status = ?, result_summary_json = ?, error_message = ?, started_at = ?, completed_at = ?
                   WHERE id = ? AND owner_user_id = ?""",
                (target.value, summary_json, error, started_at, completed_at, current.id, current.owner_user_id),
            )
        return self.get_detection_task(owner_user_id, task_id)

    def register_image(
        self,
        owner_user_id: str,
        patient_id: str,
        task_id: str,
        *,
        original_name: str,
        storage_key: str,
        mime_type: str,
        sha256: str,
        byte_size: int,
        width: int | None = None,
        height: int | None = None,
        metadata_scrubbed: bool = False,
        image_id: str | None = None,
    ) -> ImageAsset:
        task = self.get_detection_task(owner_user_id, task_id)
        if task.patient_id != _identifier(patient_id):
            raise RecordNotFoundError("检测任务不属于该患者档案。")
        digest = str(sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(digest):
            raise ValueError("影像 SHA-256 摘要无效。")
        size = int(byte_size)
        if size < 0:
            raise ValueError("影像文件大小不能为负数。")
        image_width = int(width) if width is not None else None
        image_height = int(height) if height is not None else None
        if image_width is not None and image_width <= 0:
            raise ValueError("影像宽度必须大于零。")
        if image_height is not None and image_height <= 0:
            raise ValueError("影像高度必须大于零。")
        record = ImageAsset(
            id=_identifier(image_id, generate=True),
            owner_user_id=_identifier(owner_user_id),
            patient_id=_identifier(patient_id),
            task_id=task.id,
            original_name=Path(_required_text(original_name, "原始文件名", max_length=255)).name,
            storage_key=normalize_storage_key(storage_key),
            mime_type=_required_text(mime_type, "媒体类型", max_length=120),
            sha256=digest,
            byte_size=size,
            width=image_width,
            height=image_height,
            metadata_scrubbed=bool(metadata_scrubbed),
            created_at=_now(),
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO image_assets(
                    id, owner_user_id, patient_id, task_id, original_name, storage_key, mime_type,
                    sha256, byte_size, width, height, metadata_scrubbed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.owner_user_id,
                    record.patient_id,
                    record.task_id,
                    record.original_name,
                    record.storage_key,
                    record.mime_type,
                    record.sha256,
                    record.byte_size,
                    record.width,
                    record.height,
                    int(record.metadata_scrubbed),
                    record.created_at,
                ),
            )
        return record

    def get_image_asset(self, owner_user_id: str, image_id: str) -> ImageAsset:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM image_assets WHERE id = ? AND owner_user_id = ?",
                (_identifier(image_id), _identifier(owner_user_id)),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError("影像记录不存在。")
        return self._image_from_row(row)

    def register_report(
        self,
        owner_user_id: str,
        patient_id: str,
        task_id: str,
        *,
        file_name: str,
        report_format: str,
        storage_key: str,
        model_version: str = "",
        report_id: str | None = None,
    ) -> ReportAsset:
        task = self.get_detection_task(owner_user_id, task_id)
        if task.patient_id != _identifier(patient_id):
            raise RecordNotFoundError("检测任务不属于该患者档案。")
        record = ReportAsset(
            id=_identifier(report_id, generate=True),
            owner_user_id=_identifier(owner_user_id),
            patient_id=_identifier(patient_id),
            task_id=task.id,
            file_name=Path(_required_text(file_name, "报告文件名", max_length=255)).name,
            report_format=_required_text(report_format, "报告格式", max_length=40).lower(),
            storage_key=normalize_storage_key(storage_key),
            model_version=_optional_text(model_version, max_length=255),
            created_at=_now(),
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO report_assets(
                    id, owner_user_id, patient_id, task_id, file_name, report_format,
                    storage_key, model_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.owner_user_id,
                    record.patient_id,
                    record.task_id,
                    record.file_name,
                    record.report_format,
                    record.storage_key,
                    record.model_version,
                    record.created_at,
                ),
            )
        return record

    def get_report_asset(self, owner_user_id: str, report_id: str) -> ReportAsset:
        self.initialize()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM report_assets WHERE id = ? AND owner_user_id = ?",
                (_identifier(report_id), _identifier(owner_user_id)),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError("报告记录不存在。")
        return self._report_from_row(row)

    def list_report_assets(
        self,
        owner_user_id: str,
        *,
        patient_id: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[ReportAsset]:
        self.get_user(owner_user_id)
        query = "SELECT * FROM report_assets WHERE owner_user_id = ?"
        parameters: list[Any] = [_identifier(owner_user_id)]
        if patient_id is not None:
            self.get_patient(owner_user_id, patient_id)
            query += " AND patient_id = ?"
            parameters.append(_identifier(patient_id))
        if task_id is not None:
            self.get_detection_task(owner_user_id, task_id)
            query += " AND task_id = ?"
            parameters.append(_identifier(task_id))
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(max(1, min(1000, int(limit))))
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._report_from_row(row) for row in rows]

    @staticmethod
    def _user_from_row(row: sqlite3.Row) -> UserAccount:
        return UserAccount(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            role=UserRole(row["role"]),
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
        )

    @staticmethod
    def _patient_from_row(row: sqlite3.Row) -> PatientProfile:
        return PatientProfile(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            display_name=row["display_name"],
            external_reference=row["external_reference"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_archived=bool(row["is_archived"]),
        )

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> DetectionTask:
        return DetectionTask(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            patient_id=row["patient_id"],
            status=TaskStatus(row["status"]),
            model_name=row["model_name"],
            parameters=_load_json_object(row["parameters_json"]),
            result_summary=_load_json_object(row["result_summary_json"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _image_from_row(row: sqlite3.Row) -> ImageAsset:
        return ImageAsset(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            patient_id=row["patient_id"],
            task_id=row["task_id"],
            original_name=row["original_name"],
            storage_key=row["storage_key"],
            mime_type=row["mime_type"],
            sha256=row["sha256"],
            byte_size=int(row["byte_size"]),
            width=row["width"],
            height=row["height"],
            metadata_scrubbed=bool(row["metadata_scrubbed"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _report_from_row(row: sqlite3.Row) -> ReportAsset:
        return ReportAsset(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            patient_id=row["patient_id"],
            task_id=row["task_id"],
            file_name=row["file_name"],
            report_format=row["report_format"],
            storage_key=row["storage_key"],
            model_version=row["model_version"],
            created_at=row["created_at"],
        )
