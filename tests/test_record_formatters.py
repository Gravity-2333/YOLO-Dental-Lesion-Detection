from __future__ import annotations

import unittest

from src.dental_detection.ai_defaults import SAFETY_NOTICE
from src.dental_detection.record_formatters import format_case_record, format_history_record
from src.dental_detection.record_views import history_choices_from_rows, history_id


class RecordFormatterPrivacyTests(unittest.TestCase):
    def test_history_choices_hide_internal_ids_but_keep_them_as_values(self) -> None:
        choices = history_choices_from_rows(
            [
                {
                    "检测时间": "2026-08-02T12:08:58",
                    "图片名称": "当前单图",
                    "记录ID": "history-internal-id",
                },
                {
                    "检测时间": "2026-08-02T12:09:30",
                    "图片名称": "复查牙片.png",
                    "记录ID": "history-image-id",
                },
            ]
        )

        self.assertEqual(
            choices,
            [
                ("2026-08-02 12:08:58", "history-internal-id"),
                ("2026-08-02 12:09:30 · 复查牙片.png", "history-image-id"),
            ],
        )
        self.assertEqual(history_id(choices[0][1]), "history-internal-id")
        self.assertEqual(history_id("旧标签 | history-internal-id"), "history-internal-id")

    def test_detail_lists_do_not_mix_bullet_and_ordered_markers(self) -> None:
        record = {
            "created_at": "2026-08-02T12:00:00",
            "case_id": "case-001",
            "image_name": "dental.png",
            "model": "YOLOv8m",
            "model_results": [
                {
                    "model": "YOLOv8m",
                    "detection_count": 1,
                    "detections": [
                        {
                            "class": "Caries",
                            "confidence": 0.82,
                            "x1": 1,
                            "y1": 2,
                            "x2": 30,
                            "y2": 40,
                        }
                    ],
                }
            ],
        }

        for detail in (format_case_record(record), format_history_record(record)):
            self.assertIn("1. YOLOv8m | 检测数量=1", detail)
            self.assertNotIn("- 1. YOLOv8m", detail)

        case_detail = format_case_record(record)
        self.assertIn("1. Caries（龋齿）", case_detail)
        self.assertNotIn("- 1. Caries", case_detail)

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

    def test_record_details_show_report_filename_without_local_directory(self) -> None:
        windows_path = r"C:\Users\tester\private\reports\review.zip"
        posix_path = "/srv/private/reports/review.docx"

        case_detail = format_case_record(
            {
                "case_id": "case-001",
                "image_name": "dental.png",
                "report_path": windows_path,
            }
        )
        history_detail = format_history_record(
            {
                "created_at": "2026-08-26T02:00:00",
                "image_name": "dental.png",
                "report_path": posix_path,
            }
        )

        self.assertIn("报告文件：review.zip", case_detail)
        self.assertNotIn(r"C:\Users\tester", case_detail)
        self.assertIn("报告文件：review.docx", history_detail)
        self.assertNotIn("/srv/private", history_detail)

    def test_case_detail_does_not_repeat_existing_safety_notice(self) -> None:
        detail = format_case_record(
            {
                "case_id": "case-001",
                "image_name": "dental.png",
                "suggestion": f"检测摘要：未检测到明确目标。\n\n安全声明：{SAFETY_NOTICE}",
                "safety_notice": SAFETY_NOTICE,
            }
        )

        self.assertEqual(detail.count(SAFETY_NOTICE), 1)


if __name__ == "__main__":
    unittest.main()
