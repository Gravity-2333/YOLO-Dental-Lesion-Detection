from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import gradio as gr

from src.dental_detection import gradio_files, report_center_ui
from src.dental_detection.gradio_files import remember_allowed_file_root
from src.dental_detection.personal_workspace import (
    create_personal_patient,
    ensure_personal_workspace,
    record_completed_detection,
    register_personal_report,
)
from src.dental_detection.report_center_ui import (
    REPORT_TRASH_CONFIRM_LABEL,
    REPORT_TRASH_LABEL,
    confirm_trash_report_center_item,
    load_active_report_center_item,
    load_report_center_item,
    load_tab_report_center_file,
    refresh_report_center,
    trash_report_center_item,
)
from src.dental_detection.workspace_store import RecordNotFoundError


class ReportCenterUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cache_dir = TemporaryDirectory()
        self._cache_patch = patch.object(
            gradio_files,
            "DOWNLOAD_CACHE_ROOT",
            Path(self._cache_dir.name),
        )
        self._cache_patch.start()

    def tearDown(self) -> None:
        self._cache_patch.stop()
        self._cache_dir.cleanup()

    def _create_report(
        self,
        storage_dir: str,
        patient_id: str,
        file_name: str = "single.docx",
    ):
        task = record_completed_detection(
            storage_dir,
            patient_id,
            "model-a",
            parameters={"conf": 0.25},
            result_summary={"detection_count": 1},
        )
        path = Path(storage_dir) / "reports" / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"report")
        report = register_personal_report(
            storage_dir,
            patient_id,
            task.id,
            path,
            report_format="docx",
            model_version="model-a@1",
        )
        return report, path

    def test_report_can_be_listed_downloaded_and_moved_to_trash(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            remember_allowed_file_root(temp_dir)
            report, path = self._create_report(temp_dir, workspace.patient.id)

            refreshed = refresh_report_center(temp_dir, workspace.patient.id)
            self.assertEqual(len(refreshed), 6)
            self.assertEqual(refreshed[0]["value"], report.id)
            self.assertEqual(
                refreshed[0]["choices"][0],
                (f"Word 报告 · {report_center_ui._local_timestamp(report.created_at)}", report.id),
            )
            self.assertNotIn(path.name, refreshed[0]["choices"][0][0])
            self.assertIn(path.name, refreshed[1])
            self.assertIn("record-table", refreshed[1])
            self.assertTrue(refreshed[3]["visible"])

            metadata_only = refresh_report_center(
                temp_dir,
                workspace.patient.id,
                include_file=False,
            )
            self.assertFalse(metadata_only[3]["visible"])

            active_detail, active_file, _, _ = load_active_report_center_item(
                "",
                temp_dir,
                workspace.patient.id,
            )
            self.assertIn("model-a@1", active_detail)
            self.assertTrue(active_file["visible"])

            no_pending_file = load_tab_report_center_file(
                "",
                temp_dir,
                workspace.patient.id,
            )
            self.assertEqual(no_pending_file, gr.update())

            initial_file = load_tab_report_center_file(
                report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertTrue(initial_file["visible"])
            self.assertEqual(Path(initial_file["value"]).name, path.name)

            detail, file_update, feedback, trash_update = load_report_center_item(
                report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertIn("model-a@1", detail)
            self.assertNotIn("检测任务", detail)
            self.assertNotIn(report.task_id, detail)
            self.assertTrue(file_update["visible"])
            self.assertEqual(feedback, "")
            self.assertTrue(trash_update["interactive"])
            self.assertEqual(trash_update["value"], REPORT_TRASH_LABEL)

            second_report, second_path = self._create_report(
                temp_dir,
                workspace.patient.id,
                "second.docx",
            )
            selected_file = load_tab_report_center_file(
                second_report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertEqual(Path(selected_file["value"]).name, second_path.name)

            removed = trash_report_center_item(report.id, temp_dir, workspace.patient.id)
            self.assertIn("回收站", removed[4])
            self.assertFalse(path.exists())
            self.assertEqual(len(list((Path(temp_dir) / "reports_trash").glob("*.docx"))), 1)
            with self.assertRaises(RecordNotFoundError):
                workspace.store.get_report_asset(workspace.user.id, report.id)

    def test_report_trash_requires_two_clicks_for_the_same_target(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            report, path = self._create_report(temp_dir, workspace.patient.id)

            armed = confirm_trash_report_center_item(
                report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertEqual(len(armed), 7)
            self.assertTrue(path.exists())
            self.assertEqual(armed[-2]["value"], REPORT_TRASH_CONFIRM_LABEL)

            mismatched = confirm_trash_report_center_item(
                report.id,
                temp_dir,
                "another-patient",
                armed[-1],
            )
            self.assertTrue(path.exists())
            self.assertNotEqual(mismatched[-1], armed[-1])

            completed = confirm_trash_report_center_item(
                report.id,
                temp_dir,
                workspace.patient.id,
                armed[-1],
            )
            self.assertFalse(path.exists())
            self.assertEqual(completed[-2]["value"], REPORT_TRASH_LABEL)
            self.assertEqual(completed[-1], {})

    def test_report_access_is_scoped_to_selected_patient(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            other = create_personal_patient(temp_dir, "家人")
            report, _ = self._create_report(temp_dir, workspace.patient.id)

            with self.assertRaises(gr.Error):
                load_report_center_item(report.id, temp_dir, other.id)

    def test_report_refresh_reuses_file_status_checks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            self._create_report(temp_dir, workspace.patient.id)
            original_status = report_center_ui._file_status

            with patch.object(
                report_center_ui,
                "_file_status",
                side_effect=original_status,
            ) as status_mock:
                refresh_report_center(temp_dir, workspace.patient.id)

            self.assertEqual(status_mock.call_count, 2)

    def test_reports_created_in_the_same_second_receive_compact_sequence_labels(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            first, _ = self._create_report(temp_dir, workspace.patient.id, "first.docx")
            second, _ = self._create_report(temp_dir, workspace.patient.id, "second.docx")
            second = replace(second, created_at=first.created_at)

            choices = report_center_ui._report_choices(
                temp_dir,
                [first, second],
                {first.id: "可用", second.id: "可用"},
            )
            timestamp = report_center_ui._local_timestamp(first.created_at)

            self.assertEqual(
                choices,
                [
                    (f"Word 报告 1/2 · {timestamp}", first.id),
                    (f"Word 报告 2/2 · {timestamp}", second.id),
                ],
            )
            self.assertNotIn("first.docx", choices[0][0])
            self.assertNotIn("second.docx", choices[1][0])

    def test_missing_report_file_can_remove_stale_record(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            report, path = self._create_report(temp_dir, workspace.patient.id)
            path.unlink()

            _, file_update, feedback, _ = load_report_center_item(
                report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertFalse(file_update["visible"])
            self.assertIn("不存在", feedback)
            removed = trash_report_center_item(report.id, temp_dir, workspace.patient.id)
            self.assertIn("失效", removed[4])


if __name__ == "__main__":
    unittest.main()
