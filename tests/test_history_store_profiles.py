from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from time import sleep
import unittest
from unittest.mock import patch

from src.dental_detection import history_store
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

    def test_limited_history_returns_latest_matching_patient_records(self) -> None:
        with TemporaryDirectory() as temp_dir:
            items = [
                _history_item("personal-self" if index % 2 == 0 else "family-1", f"task-{index}")
                for index in range(10)
            ]
            append_history_records(items, temp_dir, limit=20)

            records = list_history_records(temp_dir, "personal-self", limit=3)

            self.assertEqual([item["task_id"] for item in records], ["task-8", "task-6", "task-4"])

    def test_concurrent_appends_do_not_overwrite_each_other(self) -> None:
        with TemporaryDirectory() as temp_dir:
            original_load = history_store._load_raw_records

            def slow_load(storage_dir=None):
                records = original_load(storage_dir)
                sleep(0.03)
                return records

            with (
                patch.object(history_store, "_load_raw_records", side_effect=slow_load),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                futures = [
                    executor.submit(
                        append_history_records,
                        [_history_item("personal-self", f"task-{index}")],
                        temp_dir,
                        20,
                    )
                    for index in range(2)
                ]
                for future in futures:
                    future.result()

            records = list_history_records(temp_dir, "personal-self")
            self.assertEqual({item["task_id"] for item in records}, {"task-0", "task-1"})


if __name__ == "__main__":
    unittest.main()
