from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.dental_detection.personal_workspace import (
    PERSONAL_PATIENT_ID,
    PERSONAL_USER_ID,
    ensure_personal_workspace,
)
from src.dental_detection.workspace_models import TaskStatus, UserRole
from src.dental_detection.workspace_store import (
    InvalidTaskTransitionError,
    RecordNotFoundError,
    SCHEMA_VERSION,
    WorkspaceStore,
    normalize_storage_key,
)


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.store = WorkspaceStore(self.temp_dir.name)
        self.owner = self.store.create_user("owner", "所有者", role=UserRole.OWNER)
        self.patient = self.store.create_patient(self.owner.id, "本人")

    def test_schema_and_personal_workspace_are_idempotent(self) -> None:
        self.assertEqual(self.store.schema_version(), SCHEMA_VERSION)
        first = ensure_personal_workspace(self.temp_dir.name)
        second = ensure_personal_workspace(self.temp_dir.name)

        self.assertEqual(first.user.id, PERSONAL_USER_ID)
        self.assertEqual(first.patient.id, PERSONAL_PATIENT_ID)
        self.assertEqual(second.user, first.user)
        self.assertEqual(second.patient, first.patient)
        self.assertTrue(first.database_path.is_file())

    def test_patient_and_task_reads_are_scoped_to_owner(self) -> None:
        other = self.store.create_user("other", "其他用户")
        task = self.store.create_detection_task(
            self.owner.id,
            self.patient.id,
            "model-a",
            parameters={"conf": 0.25},
        )

        with self.assertRaises(RecordNotFoundError):
            self.store.get_patient(other.id, self.patient.id)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_detection_task(other.id, task.id)
        with self.assertRaises(RecordNotFoundError):
            self.store.create_detection_task(other.id, self.patient.id, "model-b")

        self.assertEqual(self.store.list_detection_tasks(self.owner.id), [task])
        self.assertEqual(self.store.list_detection_tasks(other.id), [])

    def test_task_status_transitions_are_explicit(self) -> None:
        task = self.store.create_detection_task(self.owner.id, self.patient.id, "model-a")
        running = self.store.update_task_status(self.owner.id, task.id, TaskStatus.RUNNING)
        completed = self.store.update_task_status(
            self.owner.id,
            task.id,
            TaskStatus.SUCCEEDED,
            result_summary={"detections": 2},
        )

        self.assertEqual(running.status, TaskStatus.RUNNING)
        self.assertIsNotNone(running.started_at)
        self.assertEqual(completed.result_summary, {"detections": 2})
        self.assertIsNotNone(completed.completed_at)
        with self.assertRaises(InvalidTaskTransitionError):
            self.store.update_task_status(self.owner.id, task.id, TaskStatus.FAILED)

    def test_image_and_report_records_keep_private_relative_keys(self) -> None:
        task = self.store.create_detection_task(self.owner.id, self.patient.id, "model-a")
        image = self.store.register_image(
            self.owner.id,
            self.patient.id,
            task.id,
            original_name="xray.png",
            storage_key=f"users/{self.owner.id}/images/xray.png",
            mime_type="image/png",
            sha256="a" * 64,
            byte_size=1024,
            width=640,
            height=480,
            metadata_scrubbed=True,
        )
        report = self.store.register_report(
            self.owner.id,
            self.patient.id,
            task.id,
            file_name="report.docx",
            report_format="DOCX",
            storage_key=f"users/{self.owner.id}/reports/report.docx",
            model_version="model-a@1",
        )

        self.assertEqual(self.store.get_image_asset(self.owner.id, image.id), image)
        self.assertEqual(self.store.get_report_asset(self.owner.id, report.id), report)
        self.assertTrue(image.metadata_scrubbed)
        self.assertEqual(report.report_format, "docx")

        other = self.store.create_user("reader", "无权用户")
        with self.assertRaises(RecordNotFoundError):
            self.store.get_image_asset(other.id, image.id)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_report_asset(other.id, report.id)

    def test_storage_keys_reject_absolute_and_traversal_paths(self) -> None:
        self.assertEqual(normalize_storage_key("users/a/report.docx"), "users/a/report.docx")
        for value in ("", ".", "../secret.png", "users/../secret.png", "C:/secret.png", "/secret.png"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_storage_key(value)

    def test_workspace_database_lives_under_selected_storage_root(self) -> None:
        database_path = self.store.initialize().resolve()
        self.assertEqual(database_path.parent.name, "workspace")
        self.assertIn(Path(self.temp_dir.name).resolve(), database_path.parents)


if __name__ == "__main__":
    unittest.main()
