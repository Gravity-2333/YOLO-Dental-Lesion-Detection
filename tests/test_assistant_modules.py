from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import sleep
import unittest
from unittest.mock import patch

from src.dental_detection import assistant, settings_store
from src.dental_detection.advice import default_advice, detection_prompt
from src.dental_detection.ai_client import normalize_base_url, validate_ai_request
from src.dental_detection.ai_defaults import DEFAULT_AI_MODEL, SAFETY_NOTICE
from src.dental_detection.conversation_store import save_conversation
from src.dental_detection.settings_store import AiSettings


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


if __name__ == "__main__":
    unittest.main()
