from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
import unittest

from src.dental_detection.exporters import unique_export_root


class ExporterTests(unittest.TestCase):
    def test_concurrent_export_roots_are_claimed_atomically(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with ThreadPoolExecutor(max_workers=4) as executor:
                roots = list(
                    executor.map(
                        lambda _: unique_export_root(temp_dir, "report", "20260727_120000"),
                        range(12),
                    )
                )

            self.assertEqual(len({path.name for path in roots}), 12)
            self.assertTrue(all(path.is_dir() for path in roots))


if __name__ == "__main__":
    unittest.main()
