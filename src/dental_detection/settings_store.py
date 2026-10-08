from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
import json
from pathlib import Path
import shutil
from threading import RLock
from typing import Any

from .ai_defaults import (
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_KEY_ENV,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROMPT,
    DEFAULT_FOLLOWUP_GENERATION_PROMPT,
    DEFAULT_TITLE_GENERATION_PROMPT,
    LEGACY_FOLLOWUP_GENERATION_PROMPTS,
    LEGACY_DEFAULT_AI_PROMPTS,
    LEGACY_TITLE_GENERATION_PROMPTS,
)
from .config import DEFAULT_MODEL_PATH, PROJECT_ROOT

APP_DIR_NAME = "YOLO-Dental-Lesion-Detection"


def _resolve_app_home() -> Path:
    primary = Path.home() / APP_DIR_NAME
    try:
        primary.mkdir(parents=True, exist_ok=True)
        probe = primary / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return primary
    except OSError:
        fallback = PROJECT_ROOT.parent / f"{APP_DIR_NAME}-user-data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


APP_HOME = _resolve_app_home()
CONFIG_PATH = APP_HOME / "settings.json"
CONVERSATION_DIR = APP_HOME / "conversations"
APP_DATA_DIR_NAMES = (
    "conversations",
    "exports",
    "cases",
    "cases_trash",
    "reports",
    "reports_trash",
    "history",
    "workspace",
)
_SETTINGS_FILE_LOCK = RLock()


@dataclass
class AiSettings:
    enabled: bool = False
    base_url: str = DEFAULT_AI_BASE_URL
    model: str = DEFAULT_AI_MODEL
    key_mode: str = "环境变量"
    api_key: str = DEFAULT_AI_KEY_ENV
    save_api_key: bool = False
    auto_save: bool = True
    storage_dir: str = str(APP_HOME)
    custom_prompt: str = DEFAULT_AI_PROMPT
    advice_style: str = "简洁版"
    title_generation_mode: str = "本地规则"
    title_generation_prompt: str = DEFAULT_TITLE_GENERATION_PROMPT
    followup_generation_enabled: bool = True
    followup_generation_prompt: str = DEFAULT_FOLLOWUP_GENERATION_PROMPT
    followup_click_action: str = "填入输入框"
    task_model: str = ""
    task_temperature: float = 0.2
    task_max_tokens: int = 180
    model_mode: str = "单模型"
    enable_compare: bool = True
    show_summary: bool = False
    magnifier_enabled: bool = True
    save_history: bool = True
    history_limit: int = 100
    model_dir: str = str(PROJECT_ROOT / "models")
    primary_model_path: str = str(DEFAULT_MODEL_PATH)
    compare_model_path: str = str(
        PROJECT_ROOT
        / "models"
        / "final_candidates"
        / "yolov8m_1280_full"
        / "weights"
        / "best.pt"
    )


def storage_root(storage_dir: str | None = None) -> Path:
    if storage_dir is None:
        return APP_HOME
    value = str(storage_dir).strip()
    return Path(value).expanduser() if value else APP_HOME


def conversation_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "conversations"


def export_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "exports"


def case_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "cases"


def report_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "reports"


def history_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "history"


def ensure_app_dirs(storage_dir: str | None = None) -> Path:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    root = storage_root(storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    conversation_dir(str(root)).mkdir(parents=True, exist_ok=True)
    export_dir(str(root)).mkdir(parents=True, exist_ok=True)
    case_dir(str(root)).mkdir(parents=True, exist_ok=True)
    report_dir(str(root)).mkdir(parents=True, exist_ok=True)
    (root / "reports_trash").mkdir(parents=True, exist_ok=True)
    history_dir(str(root)).mkdir(parents=True, exist_ok=True)
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    return root


def _unique_corrupt_settings_backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = CONFIG_PATH.with_name(f"{CONFIG_PATH.stem}.{stamp}.corrupt{CONFIG_PATH.suffix}")
    counter = 1
    while backup.exists():
        backup = CONFIG_PATH.with_name(
            f"{CONFIG_PATH.stem}.{stamp}_{counter:02d}.corrupt{CONFIG_PATH.suffix}"
        )
        counter += 1
    return backup


def _load_settings_unlocked() -> AiSettings:
    if not CONFIG_PATH.exists():
        return AiSettings()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        # 保留损坏文件的备份，方便用户恢复
        try:
            corrupt_backup = _unique_corrupt_settings_backup()
            CONFIG_PATH.replace(corrupt_backup)
        except OSError:
            pass
        return AiSettings()
    if not isinstance(data, dict):
        return AiSettings()
    allowed = {field.name for field in fields(AiSettings)}
    defaults = AiSettings().__dict__

    # 类型校验：防止损坏的 settings.json 在模块导入阶段导致 Path(123) 等 TypeError
    _STRING_FIELDS = {
        "base_url", "model", "key_mode", "api_key",
        "custom_prompt", "advice_style", "model_mode", "title_generation_mode",
        "title_generation_prompt", "followup_generation_prompt", "task_model",
        "followup_click_action",
    }
    _PATH_FIELDS = {
        "storage_dir", "model_dir",
        "primary_model_path", "compare_model_path",
    }
    _BOOL_FIELDS = {
        "enabled", "save_api_key", "auto_save", "enable_compare", "show_summary",
        "magnifier_enabled", "save_history", "followup_generation_enabled",
    }
    _INT_FIELDS = {"history_limit", "task_max_tokens"}
    _FLOAT_FIELDS = {"task_temperature"}

    filtered: dict[str, Any] = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key in _STRING_FIELDS:
            if isinstance(value, (int, float, bool)):
                filtered[key] = str(value)
            elif isinstance(value, str):
                filtered[key] = value
            # 非字符串/数字/布尔类型（列表、字典等）丢弃，使用默认值
        elif key in _PATH_FIELDS:
            if isinstance(value, str) and value.strip():
                filtered[key] = value
        elif key in _BOOL_FIELDS:
            if isinstance(value, bool):
                filtered[key] = value
            elif isinstance(value, str):
                filtered[key] = value.lower() in {"true", "1", "yes", "on"}
            elif isinstance(value, (int, float)):
                filtered[key] = bool(value)
            # 其他类型丢弃
        elif key in _INT_FIELDS:
            try:
                lower, upper = (1, 1000) if key == "history_limit" else (32, 800)
                filtered[key] = max(lower, min(upper, int(value)))
            except (TypeError, ValueError):
                pass
        elif key in _FLOAT_FIELDS:
            try:
                filtered[key] = max(0.0, min(2.0, float(value)))
            except (TypeError, ValueError):
                pass
        else:
            filtered[key] = value
    if filtered.get("key_mode") not in {"环境变量", "直接 Key 值"}:
        filtered.pop("key_mode", None)
    if filtered.get("model_mode") not in {"单模型", "对比模型"}:
        filtered.pop("model_mode", None)
    if filtered.get("advice_style") not in {"简洁版", "医生版", "患者版"}:
        filtered.pop("advice_style", None)
    if filtered.get("title_generation_mode") not in {"本地规则", "AI 自动生成"}:
        filtered.pop("title_generation_mode", None)
    if filtered.get("followup_click_action") not in {"填入输入框", "直接发送"}:
        filtered.pop("followup_click_action", None)
    if filtered.get("custom_prompt") in LEGACY_DEFAULT_AI_PROMPTS:
        filtered["custom_prompt"] = DEFAULT_AI_PROMPT
    if filtered.get("title_generation_prompt") in LEGACY_TITLE_GENERATION_PROMPTS:
        filtered["title_generation_prompt"] = DEFAULT_TITLE_GENERATION_PROMPT
    if filtered.get("followup_generation_prompt") in LEGACY_FOLLOWUP_GENERATION_PROMPTS:
        filtered["followup_generation_prompt"] = DEFAULT_FOLLOWUP_GENERATION_PROMPT
    return AiSettings(**{**defaults, **filtered})


def load_settings() -> AiSettings:
    with _SETTINGS_FILE_LOCK:
        return _load_settings_unlocked()


def save_settings(settings: AiSettings, *, migrate_data: bool = True) -> Path:
    with _SETTINGS_FILE_LOCK:
        return _save_settings_unlocked(settings, migrate_data=migrate_data)


def _save_settings_unlocked(settings: AiSettings, *, migrate_data: bool = True) -> Path:
    previous = _load_settings_unlocked() if CONFIG_PATH.exists() else AiSettings()
    if migrate_data:
        migrate_storage(previous.storage_dir, settings.storage_dir)
    ensure_app_dirs(settings.storage_dir)
    data = settings.__dict__.copy()
    if settings.key_mode == "直接 Key 值" and not settings.save_api_key:
        data["api_key"] = ""

    # 原子写入：先写临时文件，成功后再替换，防止写入中断导致配置损坏
    content = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(CONFIG_PATH)
    return CONFIG_PATH


def _is_empty_dir(path: Path) -> bool:
    return path.exists() and path.is_dir() and not any(path.iterdir())


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except (OSError, RuntimeError):
        return False


def _contains_path(parent: Path, child: Path) -> bool:
    try:
        parent_resolved = parent.resolve()
        child_resolved = child.resolve()
    except (OSError, RuntimeError):
        return False
    return parent_resolved == child_resolved or parent_resolved in child_resolved.parents


def _move_contents(source: Path, target: Path, skip_roots: set[Path] | None = None) -> None:
    if _same_resolved_path(source, target):
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if skip_roots and any(_contains_path(skip_root, child) for skip_root in skip_roots):
            continue
        destination = target / child.name
        if child.is_dir() and destination.exists() and destination.is_dir():
            _move_contents(child, destination, skip_roots)
            if _is_empty_dir(child):
                child.rmdir()
        elif not destination.exists():
            shutil.move(str(child), str(destination))
        else:
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.move(str(child), str(target / f"{child.stem}_{suffix}{child.suffix}"))


def _move_app_data_dirs(old_root: Path, new_root: Path) -> None:
    skip_roots = {new_root} if old_root in new_root.parents else None
    for child_name in APP_DATA_DIR_NAMES:
        source = old_root / child_name
        if not source.exists() or not source.is_dir():
            continue
        try:
            source_resolved = source.resolve()
        except OSError:
            continue
        if source_resolved == new_root or new_root in source_resolved.parents:
            continue
        _move_contents(source, new_root / child_name, skip_roots)
        if _is_empty_dir(source):
            source.rmdir()


def _managed_data_target(source: Path, new_root: Path) -> Path | None:
    name = source.name
    if name not in APP_DATA_DIR_NAMES:
        return None
    return new_root / name


def migrate_storage(old_storage_dir: str | None, new_storage_dir: str | None) -> None:
    old_root = storage_root(old_storage_dir).resolve()
    new_root = storage_root(new_storage_dir).resolve()
    if old_root == new_root or not old_root.exists() or not old_root.is_dir():
        return
    direct_target = _managed_data_target(old_root, new_root)
    if direct_target is not None:
        if _same_resolved_path(old_root, direct_target):
            return
        skip_roots = {new_root} if old_root in new_root.parents else None
        _move_contents(old_root, direct_target, skip_roots)
        if _is_empty_dir(old_root):
            old_root.rmdir()
        return
    if old_root == APP_HOME.resolve():
        _move_app_data_dirs(old_root, new_root)
        return
    if old_root in new_root.parents:
        # 新目录位于旧目录内部时，只迁移项目管理的数据目录，并跳过新目录自身。
        new_root.mkdir(parents=True, exist_ok=True)
        for child_name in APP_DATA_DIR_NAMES:
            child = old_root / child_name
            if not child.exists() or not child.is_dir():
                continue
            try:
                child_resolved = child.resolve()
            except OSError:
                continue
            if child_resolved == new_root or new_root in child_resolved.parents:
                continue
            destination = new_root / child.name
            if child.is_dir() and destination.exists() and destination.is_dir():
                _move_contents(child, destination)
                if _is_empty_dir(child):
                    child.rmdir()
            elif not destination.exists():
                shutil.move(str(child), str(destination))
            else:
                suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                shutil.move(str(child), str(new_root / f"{child.stem}_{suffix}{child.suffix}"))
        return

    if _is_empty_dir(old_root):
        old_root.rmdir()
        return
    _move_app_data_dirs(old_root, new_root)
    if _is_empty_dir(old_root):
        old_root.rmdir()
