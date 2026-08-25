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
            _, message, _ = app.export_single_report(state, "当前单图", temp_dir)
            zip_path = Path(message.split("：", 1)[1])
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
