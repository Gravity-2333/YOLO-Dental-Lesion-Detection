from __future__ import annotations

import inspect
from dataclasses import fields
import unittest

import app
from src.dental_detection.record_views import case_table_html
from src.dental_detection.ui_assets import CSS_BUNDLE_FILES, load_workbench_css, load_workbench_js
from src.dental_detection.ui_contracts import (
    COMMON_INPUT_KEYS,
    COMMON_OUTPUT_KEYS,
    COMMON_OUTPUT_QUALITY_INDEX,
    common_input_components,
    common_output_values,
)
from src.dental_detection.ui_constants import DETECTION_TABLE_COLUMNS
from src.dental_detection.ui_content import (
    AI_CHAT_INTRO_HTML,
    APP_HEADER_HTML,
    CASE_INTRO_HTML,
    WORKBENCH_HELP_TEXT,
    section_heading,
)
from src.dental_detection.ui_settings_page import AI_REQUEST_KEYS, SettingsComponents
from src.dental_detection.ui_workbench_page import WorkbenchComponents


class UiAssetTests(unittest.TestCase):
    def test_css_bundle_is_complete_and_ordered(self) -> None:
        self.assertTrue(all(path.is_file() for path in CSS_BUNDLE_FILES))
        css = load_workbench_css()
        self.assertLess(css.index(":root"), css.index(".gradio-container"))
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn(".settings-card > .settings-card", css)

    def test_javascript_bundle_loads(self) -> None:
        self.assertIn("MutationObserver", load_workbench_js())


class UiContractTests(unittest.TestCase):
    def test_common_output_contract_preserves_declared_order(self) -> None:
        values = {key: key for key in reversed(COMMON_OUTPUT_KEYS)}
        self.assertEqual(common_output_values(values), COMMON_OUTPUT_KEYS)

    def test_common_output_contract_rejects_missing_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少"):
            common_output_values({})

    def test_common_input_contract_preserves_callback_signature_order(self) -> None:
        values = {key: key for key in reversed(COMMON_INPUT_KEYS)}
        self.assertEqual(tuple(common_input_components(values)), COMMON_INPUT_KEYS)
        self.assertEqual(tuple(inspect.signature(app.run_single_detection).parameters)[1:], COMMON_INPUT_KEYS)
        self.assertEqual(tuple(inspect.signature(app.run_batch_detection).parameters)[1:], COMMON_INPUT_KEYS)

    def test_quality_index_is_derived_from_contract(self) -> None:
        self.assertEqual(COMMON_OUTPUT_KEYS[COMMON_OUTPUT_QUALITY_INDEX], "quality")

    def test_patient_switch_clears_image_and_all_detection_outputs(self) -> None:
        values = app.clear_patient_session()
        self.assertIsNone(values[0])
        self.assertIsNone(values[1])
        self.assertEqual(values[-2:], ("", ""))
        self.assertEqual(len(values), len(COMMON_OUTPUT_KEYS) + 4)

    def test_detection_table_contract_keeps_export_order(self) -> None:
        self.assertEqual(DETECTION_TABLE_COLUMNS[0:3], ("class", "中文名称", "confidence"))

    def test_settings_components_build_named_callback_inputs(self) -> None:
        components = SettingsComponents(**{field.name: field.name for field in fields(SettingsComponents)})
        common_inputs = components.common_input_map(
            model_mode="workbench_model_mode",
            patient_id="patient_id",
            conf="conf",
            iou="iou",
            device_choice="device_choice",
            use_clahe="use_clahe",
        )

        self.assertEqual(set(common_inputs), set(COMMON_INPUT_KEYS))
        self.assertEqual(common_inputs["model_mode"], "workbench_model_mode")
        self.assertEqual(common_inputs["patient_id"], "patient_id")
        self.assertEqual(components.ai_request_inputs(), list(AI_REQUEST_KEYS))

    def test_workbench_components_supply_detection_inputs_by_name(self) -> None:
        settings = SettingsComponents(**{field.name: field.name for field in fields(SettingsComponents)})
        workbench = WorkbenchComponents(**{field.name: field.name for field in fields(WorkbenchComponents)})

        common_inputs = workbench.common_input_map(settings)

        self.assertEqual(set(common_inputs), set(COMMON_INPUT_KEYS))
        self.assertEqual(common_inputs["model_mode"], "model_mode")
        self.assertEqual(common_inputs["primary_model_path"], "primary_model_path")


class UiContentTests(unittest.TestCase):
    def test_section_heading_escapes_dynamic_text(self) -> None:
        html = section_heading("<标题>", "A&B")
        self.assertIn("&lt;标题&gt;", html)
        self.assertIn("A&amp;B", html)

    def test_shared_content_keeps_brand_and_safety_copy(self) -> None:
        self.assertIn("牙齿病变区域识别", APP_HEADER_HTML)
        self.assertIn("不能替代专业牙科医生诊断", WORKBENCH_HELP_TEXT)

    def test_user_facing_copy_avoids_internal_demo_instructions(self) -> None:
        visible_copy = "".join((APP_HEADER_HTML, AI_CHAT_INTRO_HTML, CASE_INTRO_HTML))
        self.assertNotIn("答辩", visible_copy)
        self.assertNotIn("../yolov8-train", visible_copy)
        self.assertNotIn("演示提示", visible_copy)

    def test_new_chat_clears_conversation_and_export_state(self) -> None:
        chatbot, state, message, file_update, path = app.clear_current_chat()
        self.assertEqual((chatbot, state, message, path), ([], [], "", ""))
        self.assertIsNone(file_update["value"])
        self.assertFalse(file_update["visible"])

    def test_record_tables_are_lightweight_and_lazy_until_expanded(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertIn('"结构化病例列表"', source)
        self.assertIn('"结构化历史列表"', source)
        self.assertIn('open=False,\n                        elem_classes=["compact-accordion"]', source)
        report_source = inspect.getsource(app.build_report_center)
        self.assertIn('"结构化报告列表"', report_source)
        self.assertIn('open=False,\n            elem_classes=["compact-accordion"]', report_source)
        self.assertNotIn("gr.Dataframe", report_source)

    def test_record_table_html_escapes_untrusted_values(self) -> None:
        html = case_table_html([{"病例编号": '<script>alert("x")</script>'}])
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
