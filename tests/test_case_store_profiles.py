from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest

from src.dental_detection.case_store import (
    list_case_records,
    load_case_record,
    move_case_to_trash,
    search_case_records,
)
from src.dental_detection.settings_store import case_dir, ensure_app_dirs


class CaseStoreProfileTests(unittest.TestCase):
    def test_case_lists_are_filtered_by_patient_with_legacy_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            ensure_app_dirs(temp_dir)
            root = case_dir(temp_dir)
            records = [
                ("case_legacy.json", {"case_id": "legacy", "image_name": "legacy.png"}),
                (
                    "case_self.json",
                    {"case_id": "self", "image_name": "self.png", "patient_id": "personal-self"},
                ),
                (
                    "case_family.json",
                    {"case_id": "family", "image_name": "family.png", "patient_id": "family-1"},
                ),
            ]
            for file_name, payload in records:
                (root / file_name).write_text(json.dumps(payload), encoding="utf-8")

            personal_rows = list_case_records(temp_dir, "personal-self")
            family_rows = list_case_records(temp_dir, "family-1")
            family_search = search_case_records(
                temp_dir,
                "family",
                "全部",
                "全部",
                "",
                "",
                "family-1",
            )

            self.assertEqual({row["病例编号"] for row in personal_rows}, {"legacy", "self"})
            self.assertEqual([row["病例编号"] for row in family_rows], ["family"])
            self.assertEqual([row["病例编号"] for row in family_search], ["family"])
            with self.assertRaises(FileNotFoundError):
                load_case_record(temp_dir, "case_family.json", "personal-self")
            with self.assertRaises(FileNotFoundError):
                move_case_to_trash(temp_dir, "case_family.json", "personal-self")
            self.assertTrue((root / "case_family.json").exists())


if __name__ == "__main__":
    unittest.main()
