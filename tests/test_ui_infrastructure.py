from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
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
        self.assertIn("initial_case_rows: list[dict[str, Any]] = []", source)
        self.assertIn("initial_history_rows: list[dict[str, Any]] = []", source)
        self.assertIn("case_tab.select(", source)
        self.assertIn("history_tab.select(", source)
        self.assertIn("limit=CASE_UI_LIMIT", inspect.getsource(app.refresh_case_records))
        self.assertIn("limit=HISTORY_UI_LIMIT", inspect.getsource(app.refresh_history_records))
        self.assertIn('open=False,\n                        elem_classes=["compact-accordion"]', source)
        report_source = inspect.getsource(app.build_report_center)
        self.assertIn('"结构化报告列表"', report_source)
        self.assertIn('open=False,\n            elem_classes=["compact-accordion"]', report_source)
        self.assertNotIn("gr.Dataframe", report_source)

    def test_record_table_html_escapes_untrusted_values(self) -> None:
        html = case_table_html([{"病例编号": '<script>alert("x")</script>'}])
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_user_inputs_do_not_retrigger_callbacks_from_function_updates(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertIn("model_mode.input(fn=sync_model_mode", source)
        self.assertIn("settings_model_mode.input(fn=sync_model_mode", source)
        self.assertIn("batch_select.input(", source)
        self.assertIn('concurrency_id=INFERENCE_CONCURRENCY_ID', source)
        self.assertIn('concurrency_limit=1', source)
        self.assertGreaterEqual(source.count('concurrency_id=INFERENCE_CONCURRENCY_ID'), 3)
        self.assertNotIn("model_mode.change(fn=sync_model_mode", source)
        self.assertNotIn("settings_model_mode.change(fn=sync_model_mode", source)

    def test_settings_save_does_not_move_existing_data_implicitly(self) -> None:
        source = inspect.getsource(app.save_ui_settings)
        self.assertIn("save_settings(settings, migrate_data=False)", source)

    def test_settings_save_passes_non_migrating_contract_to_store(self) -> None:
        workspace = SimpleNamespace(
            patient=SimpleNamespace(id="patient-1", display_name="测试患者", external_reference=""),
        )
        with (
            patch.object(app, "load_settings", return_value=app.AiSettings(storage_dir="old-root")),
            patch.object(app, "save_settings", return_value=Path("settings.json")) as save_mock,
            patch.object(app, "_ensure_storage_root"),
            patch.object(app, "ensure_personal_workspace", return_value=workspace),
            patch.object(app, "personal_patient_choices", return_value=[]),
            patch.object(app, "personal_archived_patient_choices", return_value=[]),
            patch.object(app, "list_case_records", return_value=[]) as case_rows_mock,
            patch.object(app, "history_rows", return_value=[]) as history_rows_mock,
        ):
            result = app.save_ui_settings(
                False,
                "",
                "",
                "环境变量",
                "",
                "",
                "",
                False,
                False,
                True,
                "new-root",
                "",
                "简洁版",
                False,
                False,
                "单模型",
                "",
                "",
                "",
                True,
                100,
            )

        save_mock.assert_called_once()
        self.assertFalse(save_mock.call_args.kwargs["migrate_data"])
        case_rows_mock.assert_not_called()
        history_rows_mock.assert_not_called()
        self.assertEqual(len(result), 22)
        self.assertEqual(result[-3:], (False, False, True))

    def test_unchanged_storage_skips_report_rescan(self) -> None:
        with patch.object(app, "refresh_report_center") as refresh_mock:
            result = app.refresh_report_center_after_storage_change(False, "unused", "patient-1")

        self.assertEqual(len(result), 6)
        refresh_mock.assert_not_called()

    def test_auto_conversation_save_uses_configured_retention_limit(self) -> None:
        with (
            patch.object(app, "load_settings", return_value=app.AiSettings(history_limit=37)),
            patch.object(app, "save_conversation") as save_mock,
        ):
            warning = app._auto_save_conversation([], "storage-root")

        self.assertEqual(warning, "")
        save_mock.assert_called_once_with([], "storage-root", retain_limit=37)

    def test_batch_upload_has_a_hard_file_count_limit(self) -> None:
        self.assertEqual(len(app._normalize_batch_files(["a"] * app.BATCH_FILE_LIMIT)), app.BATCH_FILE_LIMIT)
        with self.assertRaisesRegex(app.gr.Error, "单次最多处理"):
            app._normalize_batch_files(["a"] * (app.BATCH_FILE_LIMIT + 1))

    def test_remote_requests_do_not_open_server_native_picker(self) -> None:
        request = SimpleNamespace(client=SimpleNamespace(host="192.168.1.25"))
        with patch.object(app, "_choose_directory_dialog") as picker:
            _, feedback = app.choose_storage_dir("unused", request=request)

        picker.assert_not_called()
        self.assertIn("远程访问", feedback)

    def test_history_clear_requires_two_matching_clicks(self) -> None:
        armed = app.clear_all_history_records("storage-a", "patient-1")
        self.assertEqual(len(armed), 6)
        self.assertEqual(armed[-1]["target"], "storage-a\npatient-1")
        self.assertEqual(armed[-2]["value"], "确认清空历史")

        with patch.object(app, "clear_history_records") as clear_mock:
            rearmed = app.clear_all_history_records("storage-a", "patient-2", armed[-1])

        clear_mock.assert_not_called()
        self.assertEqual(rearmed[-1]["target"], "storage-a\npatient-2")

        with (
            patch.object(app, "_ensure_storage_root"),
            patch.object(app, "clear_history_records") as clear_mock,
        ):
            completed = app.clear_all_history_records("storage-a", "patient-1", armed[-1])

        clear_mock.assert_called_once_with("storage-a", "patient-1")
        self.assertEqual(completed[-1], {})
        self.assertEqual(completed[-2]["value"], "清空历史")

    def test_record_tab_lazy_refresh_skips_repeat_archive_scans(self) -> None:
        case_result = app.lazy_refresh_case_records(True, "unused", "patient-1")
        history_result = app.lazy_refresh_history_page(True, "unused", "patient-1")
        self.assertEqual(len(case_result), 7)
        self.assertEqual(len(history_result), 11)
        self.assertTrue(case_result[-1])
        self.assertTrue(history_result[-1])


if __name__ == "__main__":
    unittest.main()
