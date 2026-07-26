from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.dental_detection import model_files


class ModelScanSafetyTests(unittest.TestCase):
    def test_single_directory_entry_budget_bounds_scan_work(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(8):
                (root / f"model_{index:02d}.pt").write_bytes(b"weights")

            with (
                patch.object(model_files, "MAX_MODEL_ENTRIES_PER_DIRECTORY", 3),
                patch.object(model_files, "MAX_MODEL_SCAN_ENTRIES", 3),
            ):
                choices = model_files.scan_model_files(root)

        self.assertEqual(len(choices), 3)

    def test_directory_budget_stops_deep_scan(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "level-one"
            nested.mkdir()
            (nested / "best.pt").write_bytes(b"weights")

            with patch.object(model_files, "MAX_MODEL_SCAN_DIRECTORIES", 1):
                choices = model_files.scan_model_files(root)

        self.assertEqual(choices, [])


if __name__ == "__main__":
    unittest.main()
