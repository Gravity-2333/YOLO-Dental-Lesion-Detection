from __future__ import annotations

import inspect
import os
from dataclasses import fields
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

import app
from src.dental_detection.record_views import case_table_html
from src.dental_detection.settings_store import AiSettings
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
    HISTORY_INTRO_HTML,
    WORKBENCH_HELP_TEXT,
    section_heading,
)
from src.dental_detection.ui_ai_chat_page import (
    build_ai_chat_page,
    build_ai_runtime_status,
    chat_export_button_state,
)
from src.dental_detection.ui_settings_page import (
    AI_REQUEST_KEYS,
    SettingsComponents,
    build_settings_page,
)
from src.dental_detection.ui_workbench_page import (
    WorkbenchComponents,
    analysis_button_state,
    build_workbench_page,
)


class UiAssetTests(unittest.TestCase):
    def test_record_details_use_sanitized_markdown_panels(self) -> None:
        source = inspect.getsource(app.build_app)
        for component_name, label, elem_id in (
            ("case_detail", "病例详情", "case-detail"),
            ("history_detail", "历史详情", "history-detail"),
        ):
            end_marker = (
                'with gr.Tab("检测历史")'
                if component_name == "case_detail"
                else "report_center = build_report_center"
            )
            component_source = source.split(f"{component_name} = gr.Markdown(", 1)[1].split(
                end_marker, 1
            )[0]
            self.assertIn(f'label="{label}"', component_source)
            self.assertIn("sanitize_html=True", component_source)
            self.assertIn("line_breaks=True", component_source)
            self.assertIn('buttons=["copy"]', component_source)
            self.assertIn(f'elem_id="{elem_id}"', component_source)
            self.assertIn('elem_classes=["record-detail"]', component_source)

        css = load_workbench_css()
        self.assertIn(".record-detail .prose strong", css)
        self.assertNotIn('textarea[aria-label="病例详情"]', css)
        self.assertNotIn('textarea[aria-label="历史详情"]', css)

    def test_css_bundle_is_complete_and_ordered(self) -> None:
        self.assertTrue(all(path.is_file() for path in CSS_BUNDLE_FILES))
        css = load_workbench_css()
        self.assertLess(css.index(":root"), css.index(".gradio-container"))
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn(".settings-card > .settings-card", css)
        self.assertNotIn("transition: all", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_javascript_bundle_loads(self) -> None:
        javascript = load_workbench_js()
        self.assertIn("MutationObserver", javascript)
        self.assertIn('"app_id"', javascript)
        self.assertIn("window.location.reload()", javascript)
        self.assertIn("visibilitychange", javascript)
        self.assertIn("dataset.runtimeAppId", javascript)

    def test_directory_picker_buttons_have_specific_accessible_names(self) -> None:
        settings_source = inspect.getsource(build_settings_page)
        javascript = load_workbench_js()

        self.assertIn('elem_id="model-dir-picker"', settings_source)
        self.assertIn('elem_id="storage-dir-picker"', settings_source)
        self.assertIn('"选择模型目录"', javascript)
        self.assertIn('"选择存储目录"', javascript)
        self.assertIn('setAttribute("aria-label", label)', javascript)

    def test_generated_icon_buttons_use_chinese_accessible_names(self) -> None:
        javascript = load_workbench_js()

        for source, target in (
            ("Upload file", "选择文件上传"),
            ("Paste from clipboard", "从剪贴板粘贴"),
            ("Copy conversation", "复制内容"),
            ("Fullscreen", "全屏查看"),
            ("Remove Image", "移除图片"),
        ):
            with self.subTest(source=source):
                self.assertIn(f'["{source}", "{target}"]', javascript)
        self.assertIn("labelGeneratedIconButtons();", javascript)
        self.assertIn('button.setAttribute("aria-label", label)', javascript)
        self.assertIn('button.setAttribute("title", label)', javascript)
        self.assertIn('document.querySelectorAll(".image-container > button")', javascript)
        self.assertIn('button.setAttribute("aria-label", "查看图片")', javascript)
        self.assertIn('button.setAttribute("title", "查看图片")', javascript)
        self.assertIn("labelImageButtons();", javascript)

    def test_truncated_path_fields_expose_the_full_value_as_a_tooltip(self) -> None:
        javascript = load_workbench_js()

        for selector in (
            '".path-row input"',
            '".path-row textarea"',
            '".path-output input"',
            '".path-output textarea"',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, javascript)
        self.assertIn('target.setAttribute("title", value)', javascript)
        self.assertIn('target.removeAttribute("title")', javascript)
        self.assertIn('["input", "change", "focusin", "pointerover"]', javascript)
        self.assertIn("labelPathValues();", javascript)

    def test_compact_action_buttons_share_a_stable_height(self) -> None:
        css = load_workbench_css()
        self.assertIn(".row.compact-row > button", css)
        self.assertIn("height: var(--primary-height) !important", css)

    def test_tablet_settings_path_rows_keep_the_desktop_alignment(self) -> None:
        css = load_workbench_css()
        tablet = css.split(
            "@media (min-width: 641px) and (max-width: 900px)",
            1,
        )[1].split("@media (max-width: 640px)", 1)[0]

        self.assertIn(
            "grid-template-columns: minmax(0, 1fr) 44px 132px !important",
            tablet.split(".path-picker-row", 1)[1],
        )
        self.assertIn("grid-template-columns: minmax(0, 1fr) 132px !important", tablet)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 152px !important", tablet)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 120px !important", tablet)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 112px !important", tablet)
        self.assertIn(".compact-row", tablet)
        self.assertIn("min-width: 104px !important", tablet)
        self.assertIn(".row.settings-actions > button", tablet)
        self.assertIn("min-width: 160px !important", tablet)

        settings_source = inspect.getsource(app.build_settings_page)
        self.assertEqual(settings_source.count('"path-picker-row"'), 2)

    def test_settings_save_row_is_a_compact_page_action(self) -> None:
        css = load_workbench_css()
        rule = css.split(".settings-actions {", 1)[1].split("}", 1)[0]

        self.assertIn("justify-content: flex-end !important", rule)
        self.assertIn("padding: 10px 0 0 !important", rule)
        self.assertIn("background: transparent !important", rule)
        self.assertIn("border: 0 !important", rule)
        self.assertIn("border-top: 1px solid var(--soft-border) !important", rule)
        self.assertNotIn("border: 1px solid var(--card-border)", rule)

    def test_css_bundle_drops_retired_frontend_scaffolding(self) -> None:
        css = load_workbench_css()
        for retired_selector in (
            ".workflow-hint",
            ".demo-flow-note",
            ".notice-grid",
            ".notice-item",
            ".settings-tabs",
        ):
            with self.subTest(selector=retired_selector):
                self.assertNotIn(retired_selector, css)

    def test_comparison_image_labels_keep_dark_viewer_contrast(self) -> None:
        css = load_workbench_css()
        viewer_rule = css.split(".clinical-viewer .comparison-image-panel", 1)[1].split(
            "}",
            1,
        )[0]
        self.assertIn("background: transparent !important", viewer_rule)
        self.assertIn("border: 0 !important", viewer_rule)
        self.assertIn(
            ".clinical-viewer .comparison-image-panel > .styler",
            css,
        )


class ProjectLauncherTests(unittest.TestCase):
    def test_service_launcher_uses_hidden_background_runner(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        batch_source = (project_root / "start_project.bat").read_text(encoding="utf-8")
        launcher_source = (project_root / "scripts" / "start_project.ps1").read_text(
            encoding="utf-8"
        )
        runner_source = (project_root / "scripts" / "run_gradio_server.bat").read_text(
            encoding="utf-8"
        )
        stop_source = (project_root / "scripts" / "stop_project.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("scripts\\start_project.ps1", batch_source)
        self.assertNotIn('start "YOLO Dental Gradio"', batch_source)
        self.assertNotIn("/k", batch_source.lower())
        self.assertIn("Start-Process", launcher_source)
        self.assertIn("-WindowStyle Hidden", launcher_source)
        self.assertIn("run_gradio_server.bat", launcher_source)
        self.assertIn("-RedirectStandardOutput", launcher_source)
        self.assertIn("-RedirectStandardError", launcher_source)
        self.assertIn('set "PYTHONUNBUFFERED=1"', runner_source)
        self.assertIn("run_gradio_server.bat", stop_source)

    def test_service_launcher_reports_immediate_runner_failure(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows launcher contract")
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            self.skipTest("PowerShell is unavailable")

        project_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script_dir = temp_root / "scripts"
            script_dir.mkdir()
            launcher = script_dir / "start_project.ps1"
            shutil.copy2(project_root / "scripts" / "start_project.ps1", launcher)
            failing_runner = script_dir / "fail-immediately.bat"
            failing_runner.write_text(
                "@echo simulated startup failure 1>&2\r\n@exit /b 7\r\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(launcher),
                    "-RunScript",
                    str(failing_runner),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("exited immediately", completed.stderr)
        self.assertIn("simulated startup failure", completed.stderr)


class DependencyManifestTests(unittest.TestCase):
    def test_ui_regression_dependency_is_kept_out_of_runtime_manifest(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        runtime = (project_root / "requirements.txt").read_text(encoding="utf-8")
        development = (project_root / "requirements-dev.txt").read_text(encoding="utf-8")

        self.assertNotIn("playwright", runtime.casefold())
        self.assertIn("-r requirements.txt", development)
        self.assertIn("playwright", development.casefold())

    def test_final_page_screenshots_reset_scroll_before_capture(self) -> None:
        screenshot_source = (
            Path(__file__).resolve().parents[1] / "scripts" / "capture_ui_screenshots.py"
        ).read_text(encoding="utf-8")

        self.assertIn("document.activeElement.blur()", screenshot_source)
        self.assertIn("scrollingElement.scrollTop = 0", screenshot_source)
        self.assertGreaterEqual(screenshot_source.count("reset_scroll=True"), 5)

    def test_final_screenshots_cover_every_primary_page(self) -> None:
        screenshot_source = (
            Path(__file__).resolve().parents[1] / "scripts" / "capture_ui_screenshots.py"
        ).read_text(encoding="utf-8")

        for tab_name, filename in (
            ("病例记录", "05-cases.png"),
            ("检测历史", "06-history.png"),
            ("设置", "06-settings.png"),
        ):
            with self.subTest(tab_name=tab_name):
                self.assertIn(f'("{tab_name}", "{filename}")', screenshot_source)
        self.assertIn('name("04-ai-chat.png", suffix)', screenshot_source)
        self.assertIn('name("07-workbench-mobile.png", suffix)', screenshot_source)
        self.assertIn('name("08-settings-mobile.png", suffix)', screenshot_source)
        self.assertIn('get_by_role("button", name="更多")', screenshot_source)
        self.assertIn('get_by_role("button", name=tab_name, exact=True)', screenshot_source)
        self.assertIn('mobile.locator(".settings-actions").wait_for', screenshot_source)
        self.assertIn('check_horizontal_overflow(mobile, "移动端设置页")', screenshot_source)
        self.assertIn('full=tab_name == "检测历史"', screenshot_source)

    def test_detection_screenshot_uses_an_isolated_non_ai_session(self) -> None:
        screenshot_source = (
            Path(__file__).resolve().parents[1] / "scripts" / "capture_ui_screenshots.py"
        ).read_text(encoding="utf-8")

        self.assertIn("TemporaryDirectory", screenshot_source)
        self.assertIn("configure_isolated_detection_session", screenshot_source)
        self.assertIn('page.get_by_label("存储目录")', screenshot_source)
        self.assertIn("storage_input.fill(isolated_path", screenshot_source)
        self.assertIn("ai_enabled.uncheck", screenshot_source)
        self.assertNotIn('get_by_role("button", name="保存设置")', screenshot_source)
        self.assertEqual(screenshot_source.count("check_navigation_responsiveness(page)"), 1)


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
        common_values = values[2 : 2 + len(COMMON_OUTPUT_KEYS)]
        self.assertEqual(common_values[COMMON_OUTPUT_KEYS.index("chatbot")], [])
        self.assertEqual(common_values[COMMON_OUTPUT_KEYS.index("chat_state")], [])
        self.assertEqual(values[-3:], ("", "", ""))
        self.assertEqual(len(values), len(COMMON_OUTPUT_KEYS) + 5)

    def test_generic_result_reset_preserves_the_current_chat(self) -> None:
        values = app.clear_outputs()
        self.assertNotIn("value", values[COMMON_OUTPUT_KEYS.index("chatbot")])
        self.assertNotIn("value", values[COMMON_OUTPUT_KEYS.index("chat_state")])

    def test_storage_switch_clears_the_current_browser_session(self) -> None:
        unchanged = app.clear_session_after_storage_change(False)
        changed = app.clear_session_after_storage_change(True)

        self.assertEqual(len(unchanged), len(COMMON_OUTPUT_KEYS) + 5)
        self.assertTrue(all("value" not in update for update in unchanged))
        self.assertEqual(len(changed), len(COMMON_OUTPUT_KEYS) + 5)
        self.assertIsNone(changed[0])
        self.assertIsNone(changed[1])
        self.assertEqual(changed[-3:], ("", "", ""))
        common_values = changed[2 : 2 + len(COMMON_OUTPUT_KEYS)]
        self.assertEqual(common_values[COMMON_OUTPUT_KEYS.index("batch_state")], [])
        self.assertEqual(common_values[COMMON_OUTPUT_KEYS.index("chatbot")], [])
        self.assertEqual(common_values[COMMON_OUTPUT_KEYS.index("chat_state")], [])

    def test_patient_switch_clears_all_patient_scoped_views_before_refresh(self) -> None:
        values = app.clear_patient_workspace_views()
        self.assertEqual(len(values), 26)
        self.assertIsNone(values[0]["value"])
        self.assertIsNone(values[6]["value"])
        self.assertIsNone(values[10]["value"])
        self.assertFalse(values[4]["visible"])
        self.assertFalse(values[13]["visible"])
        self.assertFalse(values[15]["interactive"])
        self.assertEqual(values[16:18], ("", ""))
        self.assertIsNone(values[23]["value"])
        self.assertFalse(values[-1])
        self.assertTrue(app.clear_patient_workspace_views(True)[-1])

        source = inspect.getsource(app.build_app)
        self.assertEqual(source.count("fn=clear_patient_workspace_views"), 1)
        self.assertEqual(source.count("chain_patient_workspace_refresh("), 7)

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
    def test_case_actions_follow_the_selected_record(self) -> None:
        empty_delete, empty_export = app.record_action_button_state(None)
        selected_delete, selected_export = app.record_action_button_state("病例.json")
        self.assertFalse(empty_delete["interactive"])
        self.assertFalse(empty_export["interactive"])
        self.assertTrue(selected_delete["interactive"])
        self.assertTrue(selected_export["interactive"])

        source = inspect.getsource(app.build_app)
        self.assertIn(
            '"移入回收站",\n                            interactive=False,',
            source,
        )
        self.assertIn(
            '"导出病例报告",\n                            interactive=False,',
            source,
        )
        event_source = source.split("case_select.change(", 1)[1].split(
            "refresh_history_btn.click(", 1
        )[0]
        self.assertIn("fn=record_action_button_state", event_source)
        self.assertIn("inputs=case_select", event_source)
        self.assertIn("outputs=[delete_case_btn, export_case_btn]", event_source)
        self.assertIn("queue=False", event_source)
        self.assertIn('show_progress="hidden"', event_source)

    def test_history_actions_follow_the_available_records(self) -> None:
        empty_delete, empty_clear = app.record_action_button_state("")
        selected_delete, selected_clear = app.record_action_button_state("历史记录")
        self.assertFalse(empty_delete["interactive"])
        self.assertFalse(empty_clear["interactive"])
        self.assertTrue(selected_delete["interactive"])
        self.assertTrue(selected_clear["interactive"])

        source = inspect.getsource(app.build_app)
        self.assertIn(
            '"删除所选",\n                            interactive=False,',
            source,
        )
        self.assertIn(
            '"清空历史",\n                            interactive=False,',
            source,
        )
        event_source = source.split("history_select.change(", 1)[1].split(
            "delete_history_btn.click(", 1
        )[0]
        self.assertIn("fn=record_action_button_state", event_source)
        self.assertIn("inputs=history_select", event_source)
        self.assertIn("outputs=[delete_history_btn, clear_history_btn]", event_source)
        self.assertIn("queue=False", event_source)
        self.assertIn('show_progress="hidden"', event_source)

    def test_analysis_buttons_follow_uploaded_input_state(self) -> None:
        self.assertFalse(analysis_button_state(None)["interactive"])
        self.assertFalse(analysis_button_state([])["interactive"])
        self.assertTrue(analysis_button_state(object())["interactive"])
        self.assertTrue(analysis_button_state(["image.png"])["interactive"])

        page_source = inspect.getsource(build_workbench_page)
        self.assertIn('"开始分析",\n                            variant="primary",\n                            interactive=False,', page_source)
        self.assertIn('"批量分析",\n                            variant="primary",\n                            interactive=False,', page_source)

        source = inspect.getsource(app.build_app)
        single_state_source = source.split("image.change(", 1)[1].split(
            "batch_files.change(", 1
        )[0]
        batch_state_source = source.split("batch_files.change(", 1)[1].split(
            "stale_result_controls", 1
        )[0]
        for event_source, input_name, button_name in (
            (single_state_source, "image", "run_btn"),
            (batch_state_source, "batch_files", "batch_btn"),
        ):
            self.assertIn("fn=analysis_button_state", event_source)
            self.assertIn(f"inputs={input_name}", event_source)
            self.assertIn(f"outputs={button_name}", event_source)
            self.assertIn("queue=False", event_source)
            self.assertIn('show_progress="hidden"', event_source)

    def test_chat_export_button_follows_the_conversation_state(self) -> None:
        self.assertFalse(chat_export_button_state([])["interactive"])
        self.assertTrue(
            chat_export_button_state([{"role": "assistant", "content": "结果"}])[
                "interactive"
            ]
        )
        self.assertIn('"导出对话",\n                interactive=False', inspect.getsource(build_ai_chat_page))

        source = inspect.getsource(app.build_app)
        event_source = source.split("chatbot.change(", 1)[1].split("gr.on(", 1)[0]
        self.assertIn("fn=chat_export_button_state", event_source)
        self.assertIn("inputs=chatbot", event_source)
        self.assertIn("outputs=export_btn", event_source)
        self.assertIn("queue=False", event_source)
        self.assertIn('show_progress="hidden"', event_source)

        clear_source = source.split("chatbot.clear(", 1)[1].split(
            "refresh_conversation_btn.click(", 1
        )[0]
        self.assertIn("fn=clear_current_chat_with_status", clear_source)
        self.assertIn("chat_state", clear_source)
        self.assertIn("ai_runtime_status", clear_source)
        self.assertIn("cancels=chat_event", clear_source)
        self.assertIn("queue=False", clear_source)

    def test_workbench_shows_interpretation_before_technical_detection_details(self) -> None:
        source = inspect.getsource(build_workbench_page)
        insight_position = source.index('with gr.Row(elem_classes=["insight-grid"])')
        detail_position = source.index(
            'with gr.Group(elem_classes=["section-card", "result-table-card"])'
        )

        self.assertLess(insight_position, detail_position)
        self.assertIn('"查看检测明细",\n                    open=False', source)
        detail_source = source[detail_position : source.index("summary =", detail_position)]
        self.assertIn("visible_class_filter = gr.CheckboxGroup", detail_source)
        self.assertIn("det_table = gr.Dataframe", detail_source)

    def test_section_heading_escapes_dynamic_text(self) -> None:
        html = section_heading("<标题>", "A&B")
        self.assertIn("&lt;标题&gt;", html)
        self.assertIn("A&amp;B", html)

    def test_shared_content_keeps_brand_and_safety_copy(self) -> None:
        self.assertIn("牙齿病变区域识别", APP_HEADER_HTML)
        self.assertIn("不能替代专业牙科医生诊断", WORKBENCH_HELP_TEXT)

    def test_user_facing_copy_avoids_internal_demo_instructions(self) -> None:
        visible_copy = "".join(
            (APP_HEADER_HTML, AI_CHAT_INTRO_HTML, CASE_INTRO_HTML, HISTORY_INTRO_HTML)
        )
        self.assertNotIn("答辩", visible_copy)
        self.assertNotIn("../yolov8-train", visible_copy)
        self.assertNotIn("演示提示", visible_copy)

    def test_record_pages_explain_the_local_privacy_boundary(self) -> None:
        for content in (CASE_INTRO_HTML, HISTORY_INTRO_HTML):
            with self.subTest(content=content[:40]):
                self.assertIn("本机数据目录", content)
                self.assertIn("默认不随病例和历史保存", content)
                self.assertIn("不会自动上传云端", content)
                self.assertIn('class="record-boundary-strip"', content)

        source = inspect.getsource(app.build_app)
        self.assertIn("gr.HTML(HISTORY_INTRO_HTML)", source)
        self.assertNotIn("自动保存最近检测摘要，默认不保存原始上传图", source)

    def test_new_chat_clears_conversation_and_export_state(self) -> None:
        chatbot, state, message, file_update, path = app.clear_current_chat()
        self.assertEqual((chatbot, state, message, path), ([], [], "", ""))
        self.assertIsNone(file_update["value"])
        self.assertFalse(file_update["visible"])

    def test_ai_runtime_status_escapes_configuration_and_tracks_context(self) -> None:
        settings = AiSettings(
            enabled=True,
            base_url="http://127.0.0.1:8000/v1",
            model="<local-model>",
            api_key="",
        )

        empty_status = build_ai_runtime_status([], settings)
        loaded_status = build_ai_runtime_status(
            [{"role": "assistant", "content": "检测摘要"}],
            settings,
            [
                {
                    "name": "当前单图",
                    "result": {
                        "model": "model-a",
                        "detections": [{"class": "Caries", "confidence": 0.8}],
                    },
                }
            ],
            "当前单图",
        )

        self.assertIn("尚无当前检测", empty_status)
        self.assertIn("尚无对话", empty_status)
        self.assertIn("配置完整", empty_status)
        self.assertIn("&lt;local-model&gt;", empty_status)
        self.assertIn("已加载 · 1 个检测框", loaded_status)
        self.assertIn("1 条消息", loaded_status)
        self.assertIn("检测文字与提问，不含影像", loaded_status)

    def test_continue_chat_sends_current_detection_text_without_private_artifacts(self) -> None:
        batch_state = [
            {
                "name": "patient-private.png",
                "result": {
                    "model": "model-a",
                    "model_path": "C:/private/secret.pt",
                    "original": object(),
                    "detections": [
                        {
                            "class": "Caries",
                            "confidence": 0.8,
                            "x1": 1,
                            "y1": 2,
                            "x2": 3,
                            "y2": 4,
                        }
                    ],
                },
            }
        ]

        with patch.object(app, "chat_completion", return_value="已收到") as chat_mock:
            app.continue_chat(
                "请解释结果",
                [],
                True,
                "http://127.0.0.1:8000/v1",
                "local-model",
                "直接 Key 值",
                "",
                "",
                "",
                False,
                False,
                False,
                "",
                "",
                "简洁版",
                "patient-1",
                batch_state,
                "patient-private.png",
            )

        messages = chat_mock.call_args.args[1]
        system_message = messages[0]["content"]
        self.assertIn("当前检测文字上下文", system_message)
        self.assertIn("龋齿", system_message)
        self.assertNotIn("patient-private", system_message)
        self.assertNotIn("secret.pt", system_message)

    def test_api_key_mode_switch_preserves_visible_edits_without_plaintext_state(self) -> None:
        (
            env_update,
            hidden_update,
            visible_update,
            button_update,
            visible_state,
        ) = app.set_api_key_mode(
            "环境变量",
            "old-key",
            "edited-key",
            True,
        )

        self.assertTrue(env_update["visible"])
        self.assertEqual(hidden_update["value"], "edited-key")
        self.assertFalse(hidden_update["visible"])
        self.assertEqual(visible_update["value"], "")
        self.assertFalse(visible_update["visible"])
        self.assertFalse(button_update["visible"])
        self.assertFalse(visible_state)

        direct_values = app.set_api_key_mode(
            "直接 Key 值",
            hidden_update["value"],
            visible_update["value"],
            visible_state,
        )
        self.assertEqual(direct_values[1]["value"], "edited-key")
        self.assertTrue(direct_values[1]["visible"])
        self.assertEqual(direct_values[2]["value"], "")
        self.assertFalse(direct_values[-1])

    def test_hiding_direct_api_key_moves_value_back_to_password_field(self) -> None:
        shown = app.toggle_direct_key_visibility("saved-key", "", False)
        self.assertFalse(shown[0]["visible"])
        self.assertEqual(shown[1]["value"], "saved-key")
        self.assertTrue(shown[1]["visible"])
        self.assertTrue(shown[-1])

        hidden = app.toggle_direct_key_visibility(
            shown[0]["value"],
            "edited-visible-key",
            shown[-1],
        )
        self.assertEqual(hidden[0]["value"], "edited-visible-key")
        self.assertTrue(hidden[0]["visible"])
        self.assertEqual(hidden[1]["value"], "")
        self.assertFalse(hidden[1]["visible"])
        self.assertFalse(hidden[-1])

    def test_ai_tab_lazy_loads_local_conversation_history(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertIn("conversation_loaded_state", source)
        self.assertIn("ai_tab.select(", source)
        self.assertIn("load_saved_ai_conversation", source)

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
        history_hydration = source.split("history_tab.select(", 1)[1].split(
            "clear_session_btn.click(",
            1,
        )[0]
        self.assertIn("fn=lazy_refresh_history_page", history_hydration)
        self.assertIn('trigger_mode="always_last"', history_hydration)
        self.assertIn('show_progress="minimal"', history_hydration)
        self.assertIn("fn=load_tab_report_center_file", history_hydration)
        self.assertIn(").success(", history_hydration)
        self.assertIn("inputs=[report_center.report_select", history_hydration)
        self.assertIn("outputs=report_center.report_file", history_hydration)
        self.assertIn("*report_metadata_outputs", history_hydration)
        self.assertNotIn("*report_list_outputs", history_hydration)
        self.assertEqual(source.count("history_tab.select("), 1)
        self.assertNotIn("queue=False", history_hydration)
        self.assertIn("report_center.report_select.input(", source)
        self.assertNotIn("report_center.report_select.change(", source)
        report_hydration = source.split("report_center.report_select.input(", 1)[1].split(
            "report_center.trash_button.click(",
            1,
        )[0]
        report_load_event = report_hydration.split(").then(", 1)[0]
        self.assertIn("fn=load_active_report_center_item", report_load_event)
        self.assertIn('trigger_mode="always_last"', report_load_event)
        self.assertIn('show_progress="minimal"', report_load_event)
        self.assertNotIn("queue=False", report_load_event)
        self.assertIn('open=False,\n                        elem_classes=["compact-accordion"]', source)
        report_source = inspect.getsource(app.build_report_center)
        self.assertIn('"结构化报告列表"', report_source)
        self.assertIn('open=False,\n            elem_classes=["compact-accordion"]', report_source)
        self.assertNotIn("gr.Dataframe", report_source)

    def test_record_read_events_keep_only_the_latest_pending_request(self) -> None:
        source = inspect.getsource(app.build_app)
        event_ranges = (
            ("ai_tab.select(", "case_tab.select("),
            ("case_tab.select(", "history_tab.select("),
            ("refresh_conversation_btn.click(", "load_conversation_btn.click("),
            (
                "load_conversation_btn.click(",
                "gr.on(\n            triggers=[refresh_model_btn.click",
            ),
            ("refresh_case_btn.click(", "search_case_btn.click("),
            ("search_case_btn.click(", "delete_case_btn.click("),
            ("case_select.input(", "refresh_history_btn.click("),
            ("refresh_history_btn.click(", "history_select.input("),
            ("history_select.input(", "delete_history_btn.click("),
            ("report_center.refresh_button.click(", "report_center.report_select.input("),
        )

        for start, end in event_ranges:
            with self.subTest(event=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                self.assertIn('trigger_mode="always_last"', event_source)
                self.assertIn('show_progress="minimal"', event_source)

    def test_model_directory_scans_share_one_latest_request_queue(self) -> None:
        source = inspect.getsource(app.build_app)
        model_scan_event = source.split(
            "gr.on(\n            triggers=[refresh_model_btn.click",
            1,
        )[1].split("open_model_dir_btn.click(", 1)[0]
        self.assertIn("show_advanced_models.input", model_scan_event)
        self.assertIn("fn=refresh_model_choices", model_scan_event)
        self.assertIn("concurrency_limit=1", model_scan_event)
        self.assertIn("concurrency_id=MODEL_SCAN_CONCURRENCY_ID", model_scan_event)
        self.assertIn('trigger_mode="always_last"', model_scan_event)
        self.assertIn('show_progress="minimal"', model_scan_event)

        apply_card_event = source.split("apply_model_card_event = apply_model_card_btn.click(", 1)[1].split(
            "test_model_btn.click(",
            1,
        )[0]
        apply_card_primary = apply_card_event.split(").success(", 1)[0]
        self.assertIn("concurrency_limit=1", apply_card_primary)
        self.assertIn("concurrency_id=MODEL_SCAN_CONCURRENCY_ID", apply_card_primary)
        self.assertIn('trigger_mode="always_last"', apply_card_primary)
        self.assertIn('show_progress="minimal"', apply_card_primary)
        apply_selected_event = source.split("apply_selected_model_event = apply_model_btn.click(", 1)[1].split(
            "apply_model_card_event =",
            1,
        )[0]
        apply_selected_primary = apply_selected_event.split(").success(", 1)[0]
        self.assertIn("concurrency_limit=1", apply_selected_primary)
        self.assertIn("concurrency_id=MODEL_SCAN_CONCURRENCY_ID", apply_selected_primary)
        self.assertIn('trigger_mode="always_last"', apply_selected_primary)
        self.assertIn('show_progress="minimal"', apply_selected_primary)
        self.assertEqual(source.count("concurrency_id=MODEL_SCAN_CONCURRENCY_ID"), 3)

    def test_case_note_starts_compact_and_can_expand(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertIn('label="病例备注"', source)
        self.assertIn("lines=1,\n                            max_lines=3,", source)

    def test_record_table_html_escapes_untrusted_values(self) -> None:
        html = case_table_html([{"病例编号": '<script>alert("x")</script>'}])
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_user_inputs_do_not_retrigger_callbacks_from_function_updates(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertIn("model_mode.input(\n            fn=sync_model_mode", source)
        self.assertIn("settings_model_mode.input(\n            fn=sync_model_mode", source)
        self.assertIn("batch_select.input(", source)
        self.assertIn('concurrency_id=INFERENCE_CONCURRENCY_ID', source)
        self.assertIn('concurrency_limit=1', source)
        self.assertGreaterEqual(source.count('concurrency_id=INFERENCE_CONCURRENCY_ID'), 3)
        self.assertGreaterEqual(source.count('concurrency_id=AI_REQUEST_CONCURRENCY_ID'), 2)
        self.assertEqual(source.count('concurrency_id=EXPORT_CONCURRENCY_ID'), 7)
        self.assertGreaterEqual(source.count('trigger_mode="always_last"'), 3)
        self.assertIn("triggers=[chat_btn.click, chat_input.submit]", source)
        self.assertIn("cancels=chat_event", source)
        self.assertIn("queue=False", source)
        self.assertNotIn("model_mode.change(fn=sync_model_mode", source)
        self.assertNotIn("settings_model_mode.change(fn=sync_model_mode", source)
        self.assertNotIn("chat_btn.click(\n            fn=continue_chat", source)

    def test_result_invalidations_cancel_running_inference(self) -> None:
        source = inspect.getsource(app.build_app)
        cancellation_event = source.split(
            "inference_events = [single_detection_event, batch_detection_event]",
            1,
        )[1].split("def chain_detection_result_reset", 1)[0]
        self.assertIn("fn=None", cancellation_event)
        self.assertIn("cancels=inference_events", cancellation_event)
        self.assertIn("queue=False", cancellation_event)
        self.assertIn('show_progress="hidden"', cancellation_event)
        for trigger in (
            "image.input",
            "batch_files.upload",
            "primary_model_path.input",
            "conf.input",
            "model_mode.input",
            "load_example_btn.click",
            "apply_model_btn.click",
            "patient_select.input",
            "archive_patient_btn.click",
            "clear_session_btn.click",
            "save_settings_btn.click",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, cancellation_event)

        self.assertIn("single_detection_event = run_btn.click(", source)
        self.assertIn("batch_detection_event = batch_btn.click(", source)

    def test_patient_and_ai_changes_cancel_running_chat(self) -> None:
        source = inspect.getsource(app.build_app)
        chat_cancellation_event = source.split(
            "chat_event = gr.on(",
            1,
        )[1].split("clear_chat_btn.click(", 1)[0]
        self.assertIn("cancels=chat_event", chat_cancellation_event)
        self.assertIn("queue=False", chat_cancellation_event)
        self.assertIn('show_progress="hidden"', chat_cancellation_event)
        for trigger in (
            "patient_select.input",
            "archive_patient_btn.click",
            "clear_session_btn.click",
            "save_settings_btn.click",
            "ai_enabled.input",
            "base_url.input",
            "direct_api_key_hidden.input",
            "auto_save.input",
            "storage_dir.input",
            "custom_prompt.input",
            "load_conversation_btn.click",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, chat_cancellation_event)

    def test_manual_diagnostics_keep_only_latest_pending_request(self) -> None:
        source = inspect.getsource(app.build_app)
        event_ranges = (
            ("test_btn.click(", "save_settings_btn.click("),
            ("test_model_btn.click(", "default_storage_btn.click("),
        )
        for start, end in event_ranges:
            with self.subTest(event=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                self.assertIn('trigger_mode="always_last"', event_source)
                self.assertIn('show_progress="minimal"', event_source)

    def test_lightweight_ui_controls_do_not_block_the_page(self) -> None:
        source = inspect.getsource(app.build_app)
        event_ranges = (
            ("ai_enabled.input(", "key_mode.input("),
            ("key_mode.input(", "show_direct_key_btn.click("),
            ("show_direct_key_btn.click(", "model_mode_event ="),
            ("model_mode_event = model_mode.input(", "chain_detection_result_reset(model_mode_event)"),
            ("settings_model_mode_event = settings_model_mode.input(", "chain_detection_result_reset(settings_model_mode_event)"),
            ("enable_compare_event = enable_compare.input(", "chain_detection_result_reset(enable_compare_event)"),
            ("show_summary.input(", "test_btn.click("),
            ("default_storage_btn.click(", "open_storage_btn.click("),
        )
        for start, end in event_ranges:
            with self.subTest(event=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                self.assertIn("queue=False", event_source)
                self.assertIn('show_progress="hidden"', event_source)

    def test_stale_detection_resets_share_one_latest_request_queue(self) -> None:
        source = inspect.getsource(app.build_app)
        helper_source = source.split("def chain_detection_result_reset", 1)[1].split(
            "# User-only listeners",
            1,
        )[0]
        self.assertIn("return event.success(", helper_source)
        self.assertIn("concurrency_limit=1", helper_source)
        self.assertIn("concurrency_id=RESULT_RESET_CONCURRENCY_ID", helper_source)
        self.assertIn('trigger_mode="always_last"', helper_source)
        self.assertIn('show_progress="hidden"', helper_source)
        self.assertEqual(source.count("concurrency_id=RESULT_RESET_CONCURRENCY_ID"), 6)
        self.assertEqual(source.count("chain_detection_result_reset("), 6)

    def test_followup_events_avoid_full_page_progress(self) -> None:
        source = inspect.getsource(app.build_app)
        save_followups = source.split("save_settings_btn.click(", 1)[1].split(
            "chat_event =",
            1,
        )[0]
        session_clear = save_followups.split("fn=clear_session_after_storage_change", 1)[1].split(
            ").success(",
            1,
        )[0]
        self.assertIn("inputs=storage_changed_state", session_clear)
        self.assertIn("outputs=[image, batch_files, *common_outputs, case_id, case_note, chat_input]", session_clear)
        self.assertIn("queue=False", session_clear)
        self.assertIn('show_progress="hidden"', session_clear)
        for callback in (
            "refresh_report_center_after_storage_change",
            "refresh_conversations_after_storage_change",
        ):
            event_source = save_followups.split(f"fn={callback}", 1)[1].split(").success(", 1)[0]
            self.assertIn('trigger_mode="always_last"', event_source)
            self.assertIn('show_progress="minimal"', event_source)
        self.assertEqual(save_followups.count(").success("), 4)
        self.assertNotIn(").then(", save_followups)
        self.assertIn("fn=refresh_ai_runtime_status", save_followups)
        self.assertIn("queue=False", save_followups)
        self.assertIn('show_progress="hidden"', save_followups)

        for callback in (
            "reset_history_delete_confirmation",
            "reset_report_trash_confirmation",
        ):
            self.assertEqual(source.count(f"fn={callback}"), 2)
            self.assertEqual(source.count(f").then(\n            fn={callback}"), 2)
        self.assertGreaterEqual(source.count('queue=False,\n            show_progress="hidden"'), 9)

        export_ranges = (
            ("export_word_btn.click(", "download_result_btn.click("),
            ("export_report_btn.click(", "save_case_btn.click("),
        )
        for start, end in export_ranges:
            with self.subTest(export=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                self.assertIn(").success(", event_source)
                followup = event_source.split("fn=refresh_report_center", 1)[1]
                self.assertIn('trigger_mode="always_last"', followup)
                self.assertIn('show_progress="minimal"', followup)

    def test_result_view_redraws_share_one_latest_request_queue(self) -> None:
        source = inspect.getsource(app.build_app)
        event_ranges = (
            ("batch_select.input(", "visible_class_filter.input("),
            ("visible_class_filter.input(", "ai_enabled.input("),
        )
        for start, end in event_ranges:
            with self.subTest(event=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                self.assertIn("concurrency_limit=1", event_source)
                self.assertIn("concurrency_id=RESULT_VIEW_CONCURRENCY_ID", event_source)
                self.assertIn('trigger_mode="always_last"', event_source)
                self.assertIn('show_progress="minimal"', event_source)
        self.assertEqual(source.count("concurrency_id=RESULT_VIEW_CONCURRENCY_ID"), 2)

    def test_patient_view_refreshes_share_one_latest_request_queue(self) -> None:
        source = inspect.getsource(app.build_app)
        helper_source = source.split("def chain_patient_workspace_refresh", 1)[1].split(
            "# Lazy-load record stores",
            1,
        )[0]
        self.assertEqual(helper_source.count(".success("), 3)
        self.assertNotIn(".then(", helper_source)
        self.assertEqual(helper_source.count('show_progress="hidden"'), 2)
        self.assertIn("concurrency_limit=1", helper_source)
        self.assertIn("concurrency_id=PATIENT_VIEW_CONCURRENCY_ID", helper_source)
        self.assertIn('trigger_mode="always_last"', helper_source)
        self.assertIn('show_progress="minimal"', helper_source)

        clear_event = source.split("clear_session_btn.click(", 1)[1].split(
            "patient_select_event =",
            1,
        )[0]
        self.assertIn("queue=False", clear_event)
        self.assertIn('show_progress="hidden"', clear_event)
        self.assertEqual(source.count("fn=sync_patient_selections"), 3)
        self.assertGreaterEqual(source.count('show_progress="hidden"'), 6)

    def test_demo_example_load_keeps_only_latest_pending_request(self) -> None:
        source = inspect.getsource(app.build_app)
        event_source = source.split("load_example_btn.click(", 1)[1].split(
            "run_btn.click(",
            1,
        )[0]
        primary_event = event_source.split(").success(", 1)[0]
        self.assertIn("concurrency_limit=1", primary_event)
        self.assertIn('trigger_mode="always_last"', primary_event)
        self.assertIn('show_progress="minimal"', primary_event)
        reset_event = event_source.split(").success(", 1)[1]
        self.assertIn("concurrency_id=RESULT_RESET_CONCURRENCY_ID", reset_event)
        self.assertIn('trigger_mode="always_last"', reset_event)
        self.assertIn('show_progress="hidden"', reset_event)

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

    def test_settings_keep_old_config_when_new_workspace_preflight_fails(self) -> None:
        with (
            patch.object(app, "load_settings", return_value=app.AiSettings(storage_dir="old-root")),
            patch.object(app, "save_settings") as save_mock,
            patch.object(app, "_ensure_storage_root"),
            patch.object(
                app,
                "ensure_personal_workspace",
                side_effect=app.WorkspaceError("workspace database is unavailable"),
            ),
        ):
            with self.assertRaises(app.gr.Error) as raised:
                app.save_ui_settings(
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

        self.assertIn("患者工作区初始化失败", str(raised.exception))
        save_mock.assert_not_called()

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
        save_mock.assert_called_once_with(
            [],
            "storage-root",
            retain_limit=37,
            patient_id=None,
        )

    def test_manual_conversation_export_surfaces_capacity_error(self) -> None:
        with (
            patch.object(app, "_ensure_storage_root"),
            patch.object(
                app,
                "save_conversation",
                side_effect=ValueError("对话内容过大，无法保存。请新建对话后再继续。"),
            ),
        ):
            with self.assertRaisesRegex(app.gr.Error, "对话内容过大.*新建对话"):
                app.export_chat(
                    [{"role": "user", "content": "long"}],
                    "storage-root",
                )

    def test_history_limit_normalization_handles_non_finite_values(self) -> None:
        self.assertEqual(app._normalize_history_limit(float("inf")), 100)
        self.assertEqual(app._normalize_history_limit(float("-inf")), 100)
        self.assertEqual(app._normalize_history_limit(float("nan")), 100)
        self.assertEqual(app._normalize_history_limit(-5), 1)
        self.assertEqual(app._normalize_history_limit(5000), 1000)

    def test_batch_upload_has_a_hard_file_count_limit(self) -> None:
        self.assertEqual(len(app._normalize_batch_files(["a"] * app.BATCH_FILE_LIMIT)), app.BATCH_FILE_LIMIT)
        with self.assertRaisesRegex(app.gr.Error, "单次最多处理"):
            app._normalize_batch_files(["a"] * (app.BATCH_FILE_LIMIT + 1))

    def test_batch_upload_has_a_total_size_limit(self) -> None:
        oversized = SimpleNamespace(st_size=app.BATCH_TOTAL_UPLOAD_BYTES + 1)
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "stat", return_value=oversized),
        ):
            with self.assertRaisesRegex(app.gr.Error, "总大小超过"):
                app._normalize_batch_files(["large-image.tif"])

    def test_compare_results_share_identical_source_images(self) -> None:
        original = object()
        model_input = object()
        secondary_annotated = object()
        results = [
            {"original": original, "model_input": model_input, "annotated": object()},
            {"original": object(), "model_input": object(), "annotated": secondary_annotated},
        ]

        shared = app._share_source_images(results)

        self.assertIs(shared[1]["original"], original)
        self.assertIs(shared[1]["model_input"], model_input)
        self.assertIs(shared[1]["annotated"], secondary_annotated)

    def test_launch_bounds_upload_and_session_retention(self) -> None:
        launch = MagicMock(return_value=("app", "local", "share"))
        args = SimpleNamespace(server_name="127.0.0.1", server_port=7860, share=False)
        with (
            patch.object(app, "build_app", return_value=SimpleNamespace(launch=launch)),
            patch.object(app, "_workbench_theme", return_value="theme"),
            patch.object(app, "load_workbench_css", return_value="css"),
            patch.object(app, "load_workbench_js", return_value="js"),
            patch.object(app, "_allowed_file_roots", return_value=[Path("root")]),
        ):
            app.launch_app(args)

        kwargs = launch.call_args.kwargs
        self.assertEqual(kwargs["state_session_capacity"], app.STATE_SESSION_CAPACITY)
        self.assertEqual(kwargs["max_file_size"], app.MAX_UPLOAD_FILE_SIZE)
        source = inspect.getsource(app.build_app)
        self.assertGreaterEqual(source.count("time_to_live=SESSION_STATE_TTL_SECONDS"), 7)

    def test_remote_requests_do_not_open_server_native_picker(self) -> None:
        request = SimpleNamespace(client=SimpleNamespace(host="192.168.1.25"))
        with patch.object(app, "_choose_directory_dialog") as picker:
            _, feedback = app.choose_storage_dir("unused", request=request)

        picker.assert_not_called()
        self.assertIn("远程访问", feedback)

    def test_native_path_pickers_do_not_show_a_blocking_page_overlay(self) -> None:
        source = inspect.getsource(app.build_app)
        for marker in ("open_model_dir_btn.click(", "open_storage_btn.click("):
            event_source = source.split(marker, 1)[1].split(")", 1)[0]
            self.assertIn("queue=False", event_source)
            self.assertIn('show_progress="hidden"', event_source)

    def test_native_path_picker_rejects_parallel_dialogs(self) -> None:
        dialog_lock = MagicMock()
        dialog_lock.acquire.return_value = False

        with patch.object(app, "_DIRECTORY_DIALOG_LOCK", dialog_lock):
            with self.assertRaises(app.gr.Error) as raised:
                app._choose_directory_dialog("选择目录", ".")

        self.assertIn("已有路径选择器", str(raised.exception))
        dialog_lock.acquire.assert_called_once_with(blocking=False)
        dialog_lock.release.assert_not_called()

    def test_native_path_picker_releases_lock_after_open_failure(self) -> None:
        dialog_lock = MagicMock()
        dialog_lock.acquire.return_value = True

        with (
            patch.object(app, "_DIRECTORY_DIALOG_LOCK", dialog_lock),
            patch("tkinter.Tk", side_effect=RuntimeError("dialog unavailable")),
        ):
            with self.assertRaises(app.gr.Error):
                app._choose_directory_dialog("选择目录", ".")

        dialog_lock.release.assert_called_once_with()

    def test_record_mutations_share_one_serial_write_queue(self) -> None:
        source = inspect.getsource(app.build_app)
        self.assertGreaterEqual(
            source.count("concurrency_id=RECORD_WRITE_CONCURRENCY_ID"),
            10,
        )
        patient_event_ranges = (
            ("add_patient_btn.click(", "save_patient_btn.click("),
            ("save_patient_btn.click(", "archive_patient_btn.click("),
            ("archive_patient_btn.click(", "restore_patient_btn.click("),
            ("restore_patient_btn.click(", "# User-only listeners"),
        )
        for start, end in patient_event_ranges:
            with self.subTest(event=start):
                event_source = source.split(start, 1)[1].split(end, 1)[0]
                write_event = event_source.split(").success(", 1)[0]
                self.assertIn("concurrency_limit=1", write_event)
                self.assertIn("concurrency_id=RECORD_WRITE_CONCURRENCY_ID", write_event)
                self.assertIn('show_progress="minimal"', write_event)

        chat_export = source.split("export_btn.click(", 1)[1].split(
            "export_batch_btn.click(",
            1,
        )[0]
        self.assertIn("concurrency_limit=1", chat_export)
        self.assertIn("concurrency_id=EXPORT_CONCURRENCY_ID", chat_export)
        self.assertIn('show_progress="minimal"', chat_export)

    def test_missing_models_warn_without_blocking_app_startup(self) -> None:
        saved = app.AiSettings(
            primary_model_path="missing-primary.pt",
            compare_model_path="missing-compare.pt",
        )
        with patch.object(Path, "exists", return_value=False):
            issues = app.startup_model_issues(saved)

        self.assertGreaterEqual(len(issues), len(app.MODEL_REGISTRY) + 2)
        self.assertTrue(any("候选模型" in issue for issue in issues))
        self.assertTrue(any("已保存主模型" in issue for issue in issues))
        main_source = Path(app.__file__).read_text(encoding="utf-8").split(
            'if __name__ == "__main__":',
            1,
        )[1]
        self.assertNotIn("raise FileNotFoundError", main_source)
        self.assertNotIn("YOLO(", main_source)

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

    def test_history_delete_requires_two_matching_clicks(self) -> None:
        choice = "2026-07-01T10:00:00 | image.png | record-1"
        armed = app.confirm_delete_selected_history_record(choice, "storage-a", "patient-1")
        self.assertEqual(len(armed), 6)
        self.assertEqual(armed[-1]["target"], "storage-a\npatient-1\nrecord-1")
        self.assertEqual(armed[-2]["value"], "确认删除所选")

        with patch.object(app, "delete_selected_history_record") as delete_mock:
            rearmed = app.confirm_delete_selected_history_record(
                "2026-07-01T10:00:00 | other.png | record-2",
                "storage-a",
                "patient-1",
                armed[-1],
            )

        delete_mock.assert_not_called()
        self.assertEqual(rearmed[-1]["target"], "storage-a\npatient-1\nrecord-2")

        deleted_values = ("select", "table", "detail", "已删除所选历史记录。")
        with patch.object(
            app,
            "delete_selected_history_record",
            return_value=deleted_values,
        ) as delete_mock:
            completed = app.confirm_delete_selected_history_record(
                choice,
                "storage-a",
                "patient-1",
                armed[-1],
            )

        delete_mock.assert_called_once_with(choice, "storage-a", "patient-1")
        self.assertEqual(completed[:4], deleted_values)
        self.assertEqual(completed[-1], {})
        self.assertEqual(completed[-2]["value"], "删除所选")

    def test_record_tab_lazy_refresh_skips_repeat_archive_scans(self) -> None:
        case_result = app.lazy_refresh_case_records(True, "unused", "patient-1")
        history_result = app.lazy_refresh_history_page(True, "unused", "patient-1")
        self.assertEqual(len(case_result), 7)
        self.assertEqual(len(history_result), 10)
        self.assertTrue(case_result[-1])
        self.assertTrue(history_result[-1])

    def test_patient_switch_only_scans_record_views_that_were_opened(self) -> None:
        with (
            patch.object(app, "refresh_case_records") as case_mock,
            patch.object(app, "refresh_history_records") as history_mock,
            patch.object(app, "refresh_report_center") as report_mock,
            patch.object(
                app,
                "refresh_conversation_history",
                return_value=("conversation-select", "conversation-feedback"),
            ) as conversation_mock,
            patch.object(
                app,
                "load_patient_profile_form",
                return_value=("姓名", "编号", app.gr.update(interactive=True)),
            ) as profile_mock,
        ):
            result = app.refresh_patient_workspace_views(
                False,
                False,
                False,
                "storage-a",
                "patient-1",
            )

        self.assertEqual(len(result), 26)
        case_mock.assert_not_called()
        history_mock.assert_not_called()
        report_mock.assert_not_called()
        conversation_mock.assert_not_called()
        profile_mock.assert_called_once_with("patient-1", "storage-a")
        self.assertEqual(result[20], {})
        self.assertEqual(result[19]["value"], "删除所选")
        self.assertEqual(result[22], {})
        self.assertEqual(result[21]["value"], "清空历史")
        self.assertFalse(result[-1])

        case_values = tuple(f"case-{index}" for index in range(6))
        history_values = tuple(f"history-{index}" for index in range(4))
        report_values = tuple(f"report-{index}" for index in range(6))
        with (
            patch.object(app, "refresh_case_records", return_value=case_values) as case_mock,
            patch.object(app, "refresh_history_records", return_value=history_values) as history_mock,
            patch.object(app, "refresh_report_center", return_value=report_values) as report_mock,
            patch.object(
                app,
                "refresh_conversation_history",
                return_value=("conversation-select", "conversation-feedback"),
            ) as conversation_mock,
            patch.object(
                app,
                "load_patient_profile_form",
                return_value=("姓名", "编号", app.gr.update(interactive=True)),
            ),
        ):
            result = app.refresh_patient_workspace_views(
                True,
                True,
                True,
                "storage-a",
                "patient-1",
            )

        case_mock.assert_called_once_with("storage-a", "patient-1")
        history_mock.assert_called_once_with("storage-a", "patient-1")
        report_mock.assert_called_once_with("storage-a", "patient-1")
        conversation_mock.assert_called_once_with("storage-a", "patient-1")
        self.assertEqual(result[:6], case_values)
        self.assertEqual(result[6:10], history_values)
        self.assertEqual(result[10:16], report_values)
        self.assertEqual(result[-3:], ("conversation-select", "conversation-feedback", True))

    def test_storage_switch_preserves_conversation_lazy_loading(self) -> None:
        with patch.object(
            app,
            "refresh_conversation_history",
            return_value=("conversation-select", "conversation-feedback"),
        ) as conversation_mock:
            unopened = app.refresh_conversations_after_storage_change(
                True,
                False,
                "storage-a",
                "patient-1",
            )
            loaded = app.refresh_conversations_after_storage_change(
                True,
                True,
                "storage-a",
                "patient-1",
            )

        conversation_mock.assert_called_once_with("storage-a", "patient-1")
        self.assertIsNone(unopened[0]["value"])
        self.assertIn("等待加载", unopened[1])
        self.assertFalse(unopened[2])
        self.assertEqual(loaded, ("conversation-select", "conversation-feedback", True))


if __name__ == "__main__":
    unittest.main()
