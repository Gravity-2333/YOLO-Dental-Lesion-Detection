from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from src.dental_detection.personal_workspace import (
    PERSONAL_PATIENT_ID,
    PERSONAL_USER_ID,
    archive_personal_patient,
    create_personal_patient,
    ensure_personal_workspace,
    get_personal_patient,
    personal_archived_patient_choices,
    personal_patient_choices,
    record_completed_detection,
    register_personal_report,
    restore_personal_patient,
    update_personal_patient,
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

    def test_concurrent_terminal_task_updates_cannot_overwrite_each_other(self) -> None:
        task = self.store.create_detection_task(self.owner.id, self.patient.id, "model-a")
        self.store.update_task_status(self.owner.id, task.id, TaskStatus.RUNNING)
        original_get = self.store.get_detection_task
        ready = Barrier(2)

        def synchronized_get(owner_user_id: str, task_id: str):
            current = original_get(owner_user_id, task_id)
            if current.status == TaskStatus.RUNNING:
                ready.wait(timeout=5)
            return current

        with (
            patch.object(self.store, "get_detection_task", side_effect=synchronized_get),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(
                    self.store.update_task_status,
                    self.owner.id,
                    task.id,
                    status,
                )
                for status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED)
            ]
            outcomes = []
            failures = []
            for future in futures:
                try:
                    outcomes.append(future.result())
                except InvalidTaskTransitionError as exc:
                    failures.append(exc)

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn(outcomes[0].status, {TaskStatus.SUCCEEDED, TaskStatus.FAILED})
        self.assertEqual(original_get(self.owner.id, task.id).status, outcomes[0].status)

    def test_patient_updates_and_archives_stay_owner_scoped(self) -> None:
        other = self.store.create_user("other-owner", "其他所有者")
        updated = self.store.update_patient(
            self.owner.id,
            self.patient.id,
            display_name="更新名称",
            external_reference="P-100",
        )
        archived = self.store.set_patient_archived(
            self.owner.id,
            self.patient.id,
            archived=True,
        )

        self.assertEqual(updated.display_name, "更新名称")
        self.assertEqual(updated.external_reference, "P-100")
        self.assertTrue(archived.is_archived)
        self.assertEqual(self.store.list_patients(self.owner.id), [])
        with self.assertRaises(RecordNotFoundError):
            self.store.update_patient(other.id, self.patient.id, display_name="越权修改")

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
        with self.assertRaises(RecordNotFoundError):
            self.store.delete_report_asset(other.id, report.id)
        self.assertEqual(self.store.delete_report_asset(self.owner.id, report.id), report)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_report_asset(self.owner.id, report.id)

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

    def test_personal_helpers_create_profiles_and_completed_tasks(self) -> None:
        workspace = ensure_personal_workspace(self.temp_dir.name)
        patient = create_personal_patient(
            self.temp_dir.name,
            "家人",
            external_reference="P-002",
        )
        task = record_completed_detection(
            self.temp_dir.name,
            patient.id,
            "model-a",
            parameters={"conf": 0.25},
            result_summary={"detection_count": 1},
        )

        self.assertIn(("家人 · P-002", patient.id), personal_patient_choices(self.temp_dir.name))
        self.assertEqual(task.status, TaskStatus.SUCCEEDED)
        self.assertEqual(task.patient_id, patient.id)
        self.assertEqual(
            workspace.store.get_detection_task(workspace.user.id, task.id).result_summary,
            {"detection_count": 1},
        )

        updated_patient = update_personal_patient(
            self.temp_dir.name,
            patient.id,
            display_name="家庭成员",
            external_reference="P-003",
        )
        self.assertEqual(get_personal_patient(self.temp_dir.name, patient.id), updated_patient)
        archive_personal_patient(self.temp_dir.name, patient.id)
        self.assertNotIn(patient.id, {value for _, value in personal_patient_choices(self.temp_dir.name)})
        self.assertIn(patient.id, {value for _, value in personal_archived_patient_choices(self.temp_dir.name)})
        restore_personal_patient(self.temp_dir.name, patient.id)
        self.assertIn(patient.id, {value for _, value in personal_patient_choices(self.temp_dir.name)})
        with self.assertRaisesRegex(ValueError, "本人"):
            archive_personal_patient(self.temp_dir.name, PERSONAL_PATIENT_ID)

        report_path = Path(self.temp_dir.name) / "reports" / "single.docx"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(b"report")
        report = register_personal_report(
            self.temp_dir.name,
            patient.id,
            task.id,
            report_path,
            report_format="docx",
            model_version="model-a@1",
        )

        self.assertEqual(report.patient_id, patient.id)
        self.assertEqual(report.task_id, task.id)
        self.assertEqual(
            workspace.store.list_report_assets(workspace.user.id, task_id=task.id),
            [report],
        )

    def test_duplicate_patient_labels_are_numbered_without_changing_values(self) -> None:
        first = create_personal_patient(self.temp_dir.name, "家人")
        second = create_personal_patient(self.temp_dir.name, "家人")

        active_choices = personal_patient_choices(self.temp_dir.name)
        duplicate_choices = [
            (label, value)
            for label, value in active_choices
            if value in {first.id, second.id}
        ]

        self.assertEqual(
            {label for label, _ in duplicate_choices},
            {"家人 1/2", "家人 2/2"},
        )
        self.assertEqual({value for _, value in duplicate_choices}, {first.id, second.id})

        archive_personal_patient(self.temp_dir.name, first.id)
        archive_personal_patient(self.temp_dir.name, second.id)
        archived_choices = personal_archived_patient_choices(self.temp_dir.name)
        self.assertEqual({label for label, _ in archived_choices}, {"家人 1/2", "家人 2/2"})

    def test_personal_report_rejects_files_outside_storage_root(self) -> None:
        workspace = ensure_personal_workspace(self.temp_dir.name)
        task = record_completed_detection(
            self.temp_dir.name,
            workspace.patient.id,
            "model-a",
            parameters={},
            result_summary={},
        )
        with TemporaryDirectory() as outside_dir:
            outside_path = Path(outside_dir) / "outside.docx"
            outside_path.write_bytes(b"report")
            with self.assertRaisesRegex(ValueError, "数据目录"):
                register_personal_report(
                    self.temp_dir.name,
                    workspace.patient.id,
                    task.id,
                    outside_path,
                    report_format="docx",
                )


if __name__ == "__main__":
    unittest.main()
