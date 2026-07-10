from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import gradio as gr

from src.dental_detection.gradio_files import (
    can_return_file,
    ensure_storage_root,
    file_component_output,
    remember_allowed_file_root,
    safe_existing_root,
)


class GradioFileAccessTests(unittest.TestCase):
    def test_safe_existing_root_normalizes_file_to_parent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.txt"
            path.write_text("ok", encoding="utf-8")
            self.assertEqual(safe_existing_root(path), Path(temp_dir).resolve())

    def test_download_requires_explicitly_allowed_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.txt"
            path.write_text("ok", encoding="utf-8")
            self.assertFalse(can_return_file(path))
            remember_allowed_file_root(temp_dir)
            self.assertTrue(can_return_file(path))
            update = file_component_output(path)
            self.assertEqual(update["value"], str(path))
            self.assertTrue(update["visible"])

    def test_storage_root_rejects_a_file_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "not-a-directory"
            path.write_text("file", encoding="utf-8")
            with self.assertRaises(gr.Error):
                ensure_storage_root(str(path))


if __name__ == "__main__":
    unittest.main()
