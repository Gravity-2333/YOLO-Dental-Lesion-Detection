from __future__ import annotations

import inspect
import unittest

import app
from src.dental_detection.config import DEFAULT_MODEL_PATH, MODEL_REGISTRY
from src.dental_detection.model_info import build_model_cards
from src.dental_detection.model_ui import (
    build_workbench_model_status_html,
    format_device_choice_label,
)
from src.dental_detection.ui_assets import load_workbench_css


class WorkbenchModelStatusTests(unittest.TestCase):
    def test_default_device_uses_the_same_choices_as_the_workbench(self) -> None:
        choices = [("CPU", "cpu"), ("CUDA GPU 3", "cuda:3")]

        self.assertEqual(app._default_device_choice(choices), "cuda:3")

    def test_device_choice_has_a_concise_user_facing_label(self) -> None:
        self.assertEqual(format_device_choice_label("cpu"), "CPU")
        self.assertEqual(format_device_choice_label("cuda:0"), "CUDA GPU")
        self.assertEqual(format_device_choice_label("cuda:2"), "CUDA GPU 2")
        self.assertEqual(format_device_choice_label("unexpected"), "CPU")

    def test_status_html_includes_the_selected_device(self) -> None:
        cards = build_model_cards(MODEL_REGISTRY)
        selected_path = str(MODEL_REGISTRY["YOLOv8m 原始结构"]["path"])
        html = build_workbench_model_status_html(
            selected_path,
            cards,
            default_model_path=str(DEFAULT_MODEL_PATH),
            recommended_paths={str(item["path"]) for item in MODEL_REGISTRY.values()},
            device_choice="cuda:1",
        )

        self.assertIn("设备：CUDA GPU 1", html)
        self.assertIn('class="model-status-device"', html)

    def test_status_refresh_tracks_model_and_device_inputs(self) -> None:
        source = inspect.getsource(app.build_app)

        self.assertIn(
            "triggers=[primary_model_path.input, device_choice.input]",
            source,
        )
        self.assertEqual(source.count("inputs=[primary_model_path, device_choice]"), 3)
        self.assertIn("queue=False", source.split("triggers=[primary_model_path.input", 1)[1].split(")", 1)[0])
        self.assertIn(
            "grid-template-columns: minmax(240px, 1fr) auto auto auto;",
            load_workbench_css(),
        )
        self.assertIn(
            ".guide-card .workbench-model-status .model-status-device",
            load_workbench_css(),
        )


if __name__ == "__main__":
    unittest.main()
