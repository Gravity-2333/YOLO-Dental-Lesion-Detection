from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import sleep
import unittest
from unittest.mock import patch

from src.dental_detection import assistant, conversation_store, settings_store
from src.dental_detection.advice import default_advice, detection_prompt
from src.dental_detection.ai_client import _friendly_ai_error, normalize_base_url, validate_ai_request
from src.dental_detection.ai_defaults import DEFAULT_AI_MODEL, SAFETY_NOTICE
from src.dental_detection.conversation_store import (
    MAX_CONVERSATION_FILE_BYTES,
    list_conversations,
    load_conversation,
    save_conversation,
)
from src.dental_detection.error_messages import concise_error_message, friendly_error_message
from src.dental_detection.personal_workspace import PERSONAL_PATIENT_ID
from src.dental_detection.settings_store import AiSettings
from src.dental_detection.ui_ai_chat_page import (
    load_conversation_history_item,
    refresh_conversation_history,
)


class AssistantCompatibilityTests(unittest.TestCase):
    def test_facade_keeps_existing_public_imports(self) -> None:
        self.assertIs(assistant.AiSettings, AiSettings)
        self.assertIs(assistant.default_advice, default_advice)
        self.assertEqual(assistant.DEFAULT_AI_MODEL, DEFAULT_AI_MODEL)

    def test_facade_forwards_legacy_config_path_override(self) -> None:
        original = assistant.CONFIG_PATH
        try:
            with TemporaryDirectory() as temp_dir:
                bad_settings = Path(temp_dir) / "settings.json"
                bad_settings.write_bytes(b"\xff\xfe\xff")
                assistant.CONFIG_PATH = bad_settings
                assistant.load_settings()
                self.assertFalse(bad_settings.exists())
                self.assertTrue(list(Path(temp_dir).glob("settings.*.corrupt.json")))
        finally:
            assistant.CONFIG_PATH = original
            assistant.load_settings()

    def test_settings_writes_are_serialized_across_sessions(self) -> None:
        state_lock = Lock()
        active = 0
        max_active = 0

        def slow_save(settings, *, migrate_data=True):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                sleep(0.03)
                return Path("settings.json")
            finally:
                with state_lock:
                    active -= 1

        with (
            patch.object(settings_store, "_save_settings_unlocked", side_effect=slow_save),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(settings_store.save_settings, AiSettings(model=f"model-{index}"))
                for index in range(2)
            ]
            for future in futures:
                future.result()

        self.assertEqual(max_active, 1)


class AiClientTests(unittest.TestCase):
    def test_base_url_normalization_preserves_path_prefix(self) -> None:
        self.assertEqual(
            normalize_base_url("https://example.com/openai/v1/chat/completions"),
            "https://example.com/openai/v1",
        )

    def test_public_endpoint_requires_api_key(self) -> None:
        settings = AiSettings(base_url="https://example.com/v1", api_key="MISSING_TEST_KEY")
        with patch.dict("os.environ", {}, clear=True):
            ok, api_key, error = validate_ai_request(settings)
        self.assertFalse(ok)
        self.assertEqual(api_key, "")
        self.assertIn("API Key", error)

    def test_local_endpoint_allows_empty_api_key(self) -> None:
        settings = AiSettings(base_url="http://127.0.0.1:8000/v1", api_key="")
        ok, api_key, error = validate_ai_request(settings)
        self.assertTrue(ok)
        self.assertEqual(api_key, "EMPTY")
        self.assertEqual(error, "")

    def test_ai_model_errors_are_not_reported_as_yolo_file_failures(self) -> None:
        message = friendly_error_message(
            "Error code: 404 - model deepseek-chat does not exist",
            "AI 建议生成失败",
        )
        self.assertIn("AI 模型或接口配置不可用", message)
        self.assertNotIn("模型文件无法加载", message)
        self.assertIn("测试接口", message)

    def test_ai_client_maps_not_found_to_ai_configuration(self) -> None:
        not_found_error = type(
            "NotFoundError",
            (Exception,),
            {"status_code": 404},
        )("model not found")
        message = str(_friendly_ai_error(not_found_error))
        self.assertIn("AI 模型或接口地址不存在", message)
        self.assertNotIn("YOLO", message)

    def test_concise_error_keeps_action_without_possible_causes(self) -> None:
        message = concise_error_message(
            "Error code: 404 - model deepseek-chat does not exist",
            "AI 建议生成失败",
        )
        self.assertIn("AI 模型或接口配置不可用", message)
        self.assertIn("建议处理：", message)
        self.assertNotIn("可能原因：", message)


class AdviceAndConversationTests(unittest.TestCase):
    def test_advice_and_prompt_keep_safety_boundary(self) -> None:
        advice = default_advice([])
        prompt = detection_prompt([])
        self.assertIn(SAFETY_NOTICE, advice)
        self.assertIn("不接收、不分析", prompt[0]["content"])

    def test_conversation_store_writes_valid_unique_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            messages = [{"role": "user", "content": "测试"}]
            first = save_conversation(messages, temp_dir)
            second = save_conversation(messages, temp_dir)
            self.assertNotEqual(first, second)
            payload = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(payload["messages"], messages)
            self.assertEqual(payload["safety_notice"], SAFETY_NOTICE)

    def test_conversation_store_rejects_files_that_cannot_be_loaded_later(self) -> None:
        with TemporaryDirectory() as temp_dir:
            messages = [
                {
                    "role": "user",
                    "content": "x" * MAX_CONVERSATION_FILE_BYTES,
                }
            ]

            with self.assertRaisesRegex(ValueError, "内容过大"):
                save_conversation(messages, temp_dir)

            self.assertEqual(list(Path(temp_dir).rglob("dental_chat*.json")), [])

    def test_auto_conversation_retention_removes_oldest_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            messages = [{"role": "user", "content": "保留测试"}]
            manual = save_conversation(messages, temp_dir)
            first = save_conversation(messages, temp_dir, retain_limit=2)
            second = save_conversation(messages, temp_dir, retain_limit=2)
            third = save_conversation(messages, temp_dir, retain_limit=2)

            self.assertTrue(manual.exists())
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(third.exists())
            self.assertEqual(len(list(first.parent.glob("dental_chat_auto_*.json"))), 2)

    def test_conversation_history_lists_and_loads_safe_local_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first_messages = [{"role": "user", "content": "第一次复查"}]
            second_messages = [{"role": "assistant", "content": "第二次复查"}]
            first = save_conversation(first_messages, temp_dir)
            second = save_conversation(second_messages, temp_dir, retain_limit=5)

            entries = list_conversations(temp_dir)

            self.assertEqual({entry.file_name for entry in entries}, {first.name, second.name})
            self.assertTrue(any(entry.auto_saved for entry in entries))
            self.assertEqual(load_conversation(first.name, temp_dir), first_messages)
            with self.assertRaisesRegex(ValueError, "选择无效"):
                load_conversation("../settings.json", temp_dir)

    def test_conversation_list_finds_newest_entry_beyond_old_scan_boundary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings_store.ensure_app_dirs(temp_dir)
            target_dir = settings_store.conversation_dir(temp_dir)
            for index in range(500):
                (target_dir / f"dental_chat_20260101_000000_{index:06d}.json").write_text(
                    "{}",
                    encoding="utf-8",
                )
            newest = target_dir / "dental_chat_20270101_000000_000001.json"
            newest.write_text("{}", encoding="utf-8")
            with os.scandir(target_dir) as iterator:
                ordered = sorted(iterator, key=lambda item: item.name)

            with patch.object(
                conversation_store.os,
                "scandir",
                return_value=nullcontext(iter(ordered)),
            ):
                entries = list_conversations(temp_dir, limit=5)

            self.assertEqual(entries[0].file_name, newest.name)
            self.assertEqual(len(entries), 5)

    def test_conversation_writes_remain_valid_under_concurrency(self) -> None:
        with TemporaryDirectory() as temp_dir, ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    save_conversation,
                    [{"role": "user", "content": f"并发消息 {index}"}],
                    temp_dir,
                )
                for index in range(12)
            ]
            paths = [future.result() for future in futures]

            self.assertEqual(len(set(paths)), 12)
            self.assertEqual(len(list_conversations(temp_dir)), 12)
            for path in paths:
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_conversation_history_ui_restores_chat_and_clears_exports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            messages = [{"role": "user", "content": "加载这条对话"}]
            path = save_conversation(messages, temp_dir, patient_id="patient-1")
            save_conversation(messages, temp_dir, patient_id="patient-2")

            selector_update, feedback = refresh_conversation_history(temp_dir, "patient-1")
            loaded = load_conversation_history_item(path.name, temp_dir, "patient-1")

            self.assertEqual(selector_update["value"], path.name)
            self.assertEqual(
                [entry.file_name for entry in list_conversations(temp_dir, patient_id="patient-1")],
                [path.name],
            )
            self.assertIn("最近对话", feedback)
            self.assertEqual(loaded[0:2], (messages, messages))
            self.assertEqual(loaded[2], "")
            self.assertFalse(loaded[3]["visible"])
            self.assertEqual(loaded[4], "")
            with self.assertRaisesRegex(ValueError, "不属于当前患者"):
                load_conversation(path.name, temp_dir, "patient-2")

    def test_legacy_untagged_conversations_belong_only_to_personal_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            messages = [{"role": "user", "content": "患者档案功能上线前的对话"}]
            legacy_path = save_conversation(messages, temp_dir)

            personal_entries = list_conversations(temp_dir, patient_id=PERSONAL_PATIENT_ID)
            other_entries = list_conversations(temp_dir, patient_id="family-1")

            self.assertEqual([entry.file_name for entry in personal_entries], [legacy_path.name])
            self.assertEqual(other_entries, [])
            self.assertEqual(
                load_conversation(legacy_path.name, temp_dir, PERSONAL_PATIENT_ID),
                messages,
            )
            with self.assertRaisesRegex(ValueError, "不属于当前患者"):
                load_conversation(legacy_path.name, temp_dir, "family-1")


if __name__ == "__main__":
    unittest.main()
