from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import gradio as gr

from src.dental_detection.gradio_files import remember_allowed_file_root
from src.dental_detection.personal_workspace import (
    create_personal_patient,
    ensure_personal_workspace,
    record_completed_detection,
    register_personal_report,
)
from src.dental_detection.report_center_ui import (
    load_report_center_item,
    refresh_report_center,
    trash_report_center_item,
)
from src.dental_detection.workspace_store import RecordNotFoundError


class ReportCenterUiTests(unittest.TestCase):
    def _create_report(self, storage_dir: str, patient_id: str):
        task = record_completed_detection(
            storage_dir,
            patient_id,
            "model-a",
            parameters={"conf": 0.25},
            result_summary={"detection_count": 1},
        )
        path = Path(storage_dir) / "reports" / "single.docx"
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
            self.assertIn(path.name, refreshed[1])
            self.assertIn("record-table", refreshed[1])
            self.assertTrue(refreshed[3]["visible"])

            detail, file_update, feedback, trash_update = load_report_center_item(
                report.id,
                temp_dir,
                workspace.patient.id,
            )
            self.assertIn("model-a@1", detail)
            self.assertTrue(file_update["visible"])
            self.assertEqual(feedback, "")
            self.assertTrue(trash_update["interactive"])

            removed = trash_report_center_item(report.id, temp_dir, workspace.patient.id)
            self.assertIn("回收站", removed[4])
            self.assertFalse(path.exists())
            self.assertEqual(len(list((Path(temp_dir) / "reports_trash").glob("*.docx"))), 1)
            with self.assertRaises(RecordNotFoundError):
                workspace.store.get_report_asset(workspace.user.id, report.id)

    def test_report_access_is_scoped_to_selected_patient(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = ensure_personal_workspace(temp_dir)
            other = create_personal_patient(temp_dir, "家人")
            report, _ = self._create_report(temp_dir, workspace.patient.id)

            with self.assertRaises(gr.Error):
                load_report_center_item(report.id, temp_dir, other.id)

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
