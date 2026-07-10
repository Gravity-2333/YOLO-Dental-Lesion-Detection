"""Compatibility facade for AI, advice, settings, and conversation helpers.

New code should import the owning module directly. Existing callers can keep
using this module while the application is migrated incrementally.
"""

from .advice import _normalize_class_name, default_advice, detection_prompt
from .ai_client import (
    chat_completion,
    is_private_base_url,
    normalize_base_url,
    resolve_api_key,
    test_chat_completion,
    validate_ai_request,
)
from .ai_defaults import (
    CLASS_ADVICE,
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_KEY_ENV,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROMPT,
    SAFETY_NOTICE,
)
from . import conversation_store as _conversation_store
from . import settings_store as _settings_store
from .settings_store import (
    APP_DATA_DIR_NAMES,
    APP_DIR_NAME,
    APP_HOME,
    CONFIG_PATH,
    CONVERSATION_DIR,
    AiSettings,
)


def _sync_settings_globals() -> None:
    # Some integrations historically replaced these module globals in tests or
    # embedding code. Keep that behavior while settings_store owns the logic.
    _settings_store.APP_HOME = APP_HOME
    _settings_store.CONFIG_PATH = CONFIG_PATH
    _settings_store.CONVERSATION_DIR = CONVERSATION_DIR


def storage_root(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.storage_root(storage_dir)


def conversation_dir(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.conversation_dir(storage_dir)


def export_dir(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.export_dir(storage_dir)


def case_dir(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.case_dir(storage_dir)


def report_dir(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.report_dir(storage_dir)


def history_dir(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.history_dir(storage_dir)


def ensure_app_dirs(storage_dir: str | None = None):
    _sync_settings_globals()
    return _settings_store.ensure_app_dirs(storage_dir)


def load_settings():
    _sync_settings_globals()
    return _settings_store.load_settings()


def save_settings(settings: AiSettings, *, migrate_data: bool = True):
    _sync_settings_globals()
    return _settings_store.save_settings(settings, migrate_data=migrate_data)


def migrate_storage(old_storage_dir: str | None, new_storage_dir: str | None) -> None:
    _sync_settings_globals()
    _settings_store.migrate_storage(old_storage_dir, new_storage_dir)


def save_conversation(messages, storage_dir: str | None = None):
    _sync_settings_globals()
    return _conversation_store.save_conversation(messages, storage_dir)


__all__ = [
    "APP_DATA_DIR_NAMES",
    "APP_DIR_NAME",
    "APP_HOME",
    "CLASS_ADVICE",
    "CONFIG_PATH",
    "CONVERSATION_DIR",
    "DEFAULT_AI_BASE_URL",
    "DEFAULT_AI_KEY_ENV",
    "DEFAULT_AI_MODEL",
    "DEFAULT_AI_PROMPT",
    "SAFETY_NOTICE",
    "AiSettings",
    "_normalize_class_name",
    "case_dir",
    "chat_completion",
    "conversation_dir",
    "default_advice",
    "detection_prompt",
    "ensure_app_dirs",
    "export_dir",
    "history_dir",
    "is_private_base_url",
    "load_settings",
    "migrate_storage",
    "normalize_base_url",
    "report_dir",
    "resolve_api_key",
    "save_conversation",
    "save_settings",
    "storage_root",
    "test_chat_completion",
    "validate_ai_request",
]
