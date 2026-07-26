from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import gradio as gr

from src.dental_detection import gradio_files
from src.dental_detection.gradio_files import (
    allowed_file_roots,
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
            root = Path(temp_dir)
            path = root / "result.txt"
            cache = root / "cache"
            path.write_text("ok", encoding="utf-8")
            with patch.object(gradio_files, "DOWNLOAD_CACHE_ROOT", cache):
                self.assertFalse(can_return_file(path))
                remember_allowed_file_root(temp_dir)
                self.assertTrue(can_return_file(path))
                update = file_component_output(path)

                cached = Path(update["value"])
                self.assertTrue(update["visible"])
                self.assertNotEqual(cached, path)
                self.assertEqual(cached.read_text(encoding="utf-8"), "ok")
                self.assertEqual(allowed_file_roots(), [cache.resolve()])
                self.assertNotIn(root.resolve(), allowed_file_roots())

    def test_download_cache_prunes_expired_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "cache"
            expired = cache / "expired"
            expired.mkdir(parents=True)
            (expired / "report.zip").write_bytes(b"old")
            os.utime(expired, (1, 1))

            with patch.object(gradio_files, "DOWNLOAD_CACHE_ROOT", cache):
                allowed_file_roots()

            self.assertFalse(expired.exists())

    def test_storage_root_rejects_a_file_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "not-a-directory"
            path.write_text("file", encoding="utf-8")
            with self.assertRaises(gr.Error):
                ensure_storage_root(str(path))


if __name__ == "__main__":
    unittest.main()
