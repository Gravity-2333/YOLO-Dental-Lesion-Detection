from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from PIL import Image

import app
from src.dental_detection.exporters import unique_export_root


class ExporterTests(unittest.TestCase):
    def test_comparison_zip_identifies_every_model_in_user_facing_summaries(self) -> None:
        image = Image.new("RGB", (48, 32), "white")
        model_results = [
            {
                "model": model,
                "model_path": f"models/{model}.pt",
                "original": image,
                "model_input": image,
                "annotated": image,
                "detections": [],
            }
            for model in ("主模型", "对比模型")
        ]
        state = [
            {
                "name": "当前单图",
                "result": model_results[0],
                "all_results": model_results,
                "summary": {"模型结果": [{"模型": item["model"]} for item in model_results]},
                "advice": "辅助建议",
            }
        ]

        with TemporaryDirectory() as temp_dir:
            _, path_text, _ = app.export_single_report(state, "当前单图", temp_dir)
            zip_path = Path(path_text)
            with ZipFile(zip_path) as archive:
                text_summary = archive.read("summary.txt").decode("utf-8")
                html_report = archive.read("report.html").decode("utf-8")
                json_report = json.loads(archive.read("detections.json"))

        self.assertIn("使用模型: 主模型、对比模型", text_summary)
        self.assertIn("模型结果组数: 2", text_summary)
        self.assertIn("图片名称: 当前单图", text_summary)
        self.assertIn("使用模型：主模型、对比模型", html_report)
        self.assertEqual(json_report["report"]["models"], ["主模型", "对比模型"])
        self.assertEqual(json_report["report"]["image_name"], "当前单图")

    def test_user_facing_export_fields_return_direct_paths(self) -> None:
        image = Image.new("RGB", (48, 32), "white")
        state = [
            {
                "name": "当前单图",
                "result": {
                    "model": "主模型",
                    "model_path": "models/primary.pt",
                    "original": image,
                    "model_input": image,
                    "annotated": image,
                    "detections": [],
                },
                "summary": {},
                "advice": "辅助建议",
            }
        ]

        with TemporaryDirectory() as temp_dir:
            task = app.record_completed_detection(
                temp_dir, "personal-self", "主模型", parameters={}, result_summary={}
            )
            state[0].update(patient_id="personal-self", task_id=task.id)
            _, zip_path_text, state = app.export_single_report(state, "当前单图", temp_dir)
            _, word_path_text, state = app.export_word_report(state, "当前单图", temp_dir)
            _, image_path_text = app.download_result_image(state, "当前单图", temp_dir)
            case_values = app.save_case_record(state, "当前单图", "路径复验", "", temp_dir)
            _, case_path_text = app.export_selected_case_record(
                case_values[1]["value"],
                temp_dir,
            )

            for path_text in (
                zip_path_text,
                word_path_text,
                image_path_text,
                case_path_text,
            ):
                with self.subTest(path_text=path_text):
                    self.assertTrue(Path(path_text).is_file())
            self.assertEqual(case_values[0], "病例记录已保存。")

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
