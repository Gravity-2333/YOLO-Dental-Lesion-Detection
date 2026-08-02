from __future__ import annotations

import unittest

from src.dental_detection.record_formatters import format_case_record, format_history_record


class RecordFormatterPrivacyTests(unittest.TestCase):
    def test_history_detail_keeps_model_filename_without_windows_deployment_path(self) -> None:
        detail = format_history_record(
            {
                "created_at": "2026-08-02T12:00:00",
                "image_name": "dental.png",
                "model": "YOLOv8m",
                "model_results": [
                    {
                        "model": "YOLOv8m",
                        "model_path": r"C:\private\deployment\weights\best.pt",
                        "detection_count": 0,
                    }
                ],
            }
        )

        self.assertIn("模型文件=best.pt", detail)
        self.assertNotIn(r"C:\private\deployment", detail)
        self.assertNotIn("路径=", detail)

    def test_case_detail_keeps_model_filename_without_posix_deployment_path(self) -> None:
        model_summary = {
            "模型": "优化模型",
            "模型路径": "/srv/private/models/optimized.mlpackage",
            "检测数量": 1,
        }
        detail = format_case_record(
            {
                "case_id": "case-001",
                "image_name": "dental.png",
                "model_results": [model_summary],
                "summary": {"模型结果": [model_summary]},
            }
        )

        self.assertIn("模型文件=optimized.mlpackage", detail)
        self.assertNotIn("/srv/private/models", detail)
        self.assertNotIn("路径=", detail)


if __name__ == "__main__":
    unittest.main()
