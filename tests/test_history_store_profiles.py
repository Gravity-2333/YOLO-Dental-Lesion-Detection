from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from src.dental_detection.history_store import (
    append_history_records,
    clear_history_records,
    list_history_records,
    load_history_record,
    update_history_report_paths,
)


def _history_item(patient_id: str, task_id: str) -> dict:
    return {
        "name": "same-name.png",
        "patient_id": patient_id,
        "task_id": task_id,
        "result": {"model": "model-a", "detections": []},
        "summary": {"模型": "model-a"},
        "advice": "辅助建议",
    }


class HistoryStoreProfileTests(unittest.TestCase):
    def test_history_access_and_cleanup_are_scoped_by_patient(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = _history_item("personal-self", "task-self")
            second = _history_item("family-1", "task-family")
            append_history_records([first, second], temp_dir, limit=20)

            personal_records = list_history_records(temp_dir, "personal-self")
            family_records = list_history_records(temp_dir, "family-1")
            personal_id = personal_records[0]["id"]

            self.assertEqual([item["task_id"] for item in personal_records], ["task-self"])
            self.assertEqual([item["task_id"] for item in family_records], ["task-family"])
            self.assertIsNone(load_history_record(personal_id, temp_dir, "family-1"))

            changed = update_history_report_paths([second], "family-report.docx", temp_dir)
            self.assertEqual(changed, 1)
            self.assertEqual(
                list_history_records(temp_dir, "family-1")[0]["report_path"],
                "family-report.docx",
            )
            self.assertEqual(list_history_records(temp_dir, "personal-self")[0]["report_path"], "")

            clear_history_records(temp_dir, "personal-self")
            self.assertEqual(list_history_records(temp_dir, "personal-self"), [])
            self.assertEqual(len(list_history_records(temp_dir, "family-1")), 1)

    def test_legacy_history_defaults_to_personal_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            append_history_records([{"name": "legacy.png", "result": {"detections": []}}], temp_dir)

            self.assertEqual(len(list_history_records(temp_dir, "personal-self")), 1)
            self.assertEqual(list_history_records(temp_dir, "family-1"), [])


if __name__ == "__main__":
    unittest.main()
