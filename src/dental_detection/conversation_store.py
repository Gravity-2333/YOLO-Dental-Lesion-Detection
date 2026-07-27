from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import heapq
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any

from .ai_defaults import SAFETY_NOTICE
from .settings_store import conversation_dir, ensure_app_dirs


MAX_CONVERSATION_FILE_BYTES = 2 * 1024 * 1024
MAX_CONVERSATION_LIST_ITEMS = 50
_CONVERSATION_NAME = re.compile(
    r"dental_chat(?:_auto)?(?:_p[0-9a-f]{16})?_\d{8}_\d{6}_\d{6}(?:_\d+)?\.json"
)
_CONVERSATION_ORDER = re.compile(r"_(\d{8}_\d{6}_\d{6})(?:_(\d+))?\.json$")
_CONVERSATION_FILE_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class ConversationEntry:
    file_name: str
    modified_at: datetime
    auto_saved: bool


def _normalize_messages(messages: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages or []:
        if isinstance(message, dict):
            role = str(message.get("role") or "assistant")
            if role not in {"system", "user", "assistant"}:
                role = "assistant"
            normalized.append({"role": role, "content": str(message.get("content", ""))})
        elif isinstance(message, (list, tuple)) and len(message) >= 2:
            user_content, assistant_content = message[0], message[1]
            if user_content is not None and user_content != "":
                normalized.append({"role": "user", "content": str(user_content)})
            if assistant_content is not None and assistant_content != "":
                normalized.append({"role": "assistant", "content": str(assistant_content)})
        elif message is not None and message != "":
            normalized.append({"role": "assistant", "content": str(message)})
    return normalized


def _prune_conversations(target_dir: Path, retain_limit: int, pattern: str) -> None:
    files = sorted(target_dir.glob(pattern), reverse=True)
    for path in files[max(1, int(retain_limit)) :]:
        try:
            path.unlink()
        except OSError:
            continue


def _patient_tag(patient_id: str | None) -> str:
    value = str(patient_id or "").strip()
    return sha256(value.encode("utf-8")).hexdigest()[:16] if value else ""


def _conversation_order_key(file_name: str) -> tuple[str, int, str]:
    match = _CONVERSATION_ORDER.search(file_name)
    if not match:
        return "", 0, file_name
    return match.group(1), int(match.group(2) or 0), file_name


def save_conversation(
    messages: list[dict[str, str]],
    storage_dir: str | None = None,
    *,
    retain_limit: int | None = None,
    patient_id: str | None = None,
) -> Path:
    with _CONVERSATION_FILE_LOCK:
        ensure_app_dirs(storage_dir)
        target_dir = conversation_dir(storage_dir)
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S_%f")
        prefix = "dental_chat_auto" if retain_limit is not None else "dental_chat"
        patient_tag = _patient_tag(patient_id)
        if patient_tag:
            prefix = f"{prefix}_p{patient_tag}"
        path = target_dir / f"{prefix}_{stamp}.json"
        if path.exists():
            counter = 1
            while path.exists():
                path = target_dir / f"{prefix}_{stamp}_{counter:02d}.json"
                counter += 1
        payload = {
            "created_at": now.isoformat(timespec="seconds"),
            "patient_id": str(patient_id or "").strip(),
            "safety_notice": SAFETY_NOTICE,
            "messages": _normalize_messages(messages),
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if len(serialized) > MAX_CONVERSATION_FILE_BYTES:
            raise ValueError("对话内容过大，无法保存。请新建对话后再继续。")
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_bytes(serialized)
        tmp_path.replace(path)
        if retain_limit is not None:
            pattern = (
                f"dental_chat_auto_p{patient_tag}_*.json"
                if patient_tag
                else "dental_chat_auto_[0-9]*.json"
            )
            _prune_conversations(target_dir, retain_limit, pattern)
        return path


def list_conversations(
    storage_dir: str | None = None,
    *,
    limit: int = MAX_CONVERSATION_LIST_ITEMS,
    patient_id: str | None = None,
) -> list[ConversationEntry]:
    expected_tag = _patient_tag(patient_id)
    try:
        max_items = max(1, min(int(limit), MAX_CONVERSATION_LIST_ITEMS))
    except (OverflowError, TypeError, ValueError):
        max_items = MAX_CONVERSATION_LIST_ITEMS
    with _CONVERSATION_FILE_LOCK:
        ensure_app_dirs(storage_dir)
        target_dir = conversation_dir(storage_dir)
        recent: list[tuple[tuple[str, int, str], str]] = []
        try:
            with os.scandir(target_dir) as iterator:
                for item in iterator:
                    if not _CONVERSATION_NAME.fullmatch(item.name) or not item.is_file(follow_symlinks=False):
                        continue
                    marker = re.search(r"_p([0-9a-f]{16})_", item.name)
                    item_tag = marker.group(1) if marker else ""
                    if item_tag != expected_tag:
                        continue
                    candidate = (_conversation_order_key(item.name), item.name)
                    if len(recent) < max_items:
                        heapq.heappush(recent, candidate)
                    elif candidate > recent[0]:
                        heapq.heapreplace(recent, candidate)
        except OSError:
            return []
        entries: list[ConversationEntry] = []
        for _, file_name in sorted(recent, reverse=True):
            try:
                modified_at = datetime.fromtimestamp(
                    (target_dir / file_name).stat().st_mtime
                )
            except OSError:
                continue
            entries.append(
                ConversationEntry(
                    file_name=file_name,
                    modified_at=modified_at,
                    auto_saved=file_name.startswith("dental_chat_auto_"),
                )
            )
    return entries


def load_conversation(
    file_name: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> list[dict[str, str]]:
    name = str(file_name or "").strip()
    if Path(name).name != name or not _CONVERSATION_NAME.fullmatch(name):
        raise ValueError("对话记录选择无效，请刷新列表后重试。")
    expected_tag = _patient_tag(patient_id)
    marker = re.search(r"_p([0-9a-f]{16})_", name)
    item_tag = marker.group(1) if marker else ""
    if item_tag != expected_tag:
        raise ValueError("该对话记录不属于当前患者档案。")
    with _CONVERSATION_FILE_LOCK:
        ensure_app_dirs(storage_dir)
        path = conversation_dir(storage_dir) / name
        try:
            if not path.is_file():
                raise FileNotFoundError(name)
            if path.stat().st_size > MAX_CONVERSATION_FILE_BYTES:
                raise ValueError("对话记录文件过大，无法在页面中加载。")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError("对话记录已不存在，请刷新列表。") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("对话记录文件损坏或无法读取。") from exc
    if not isinstance(payload, dict):
        raise ValueError("对话记录格式无效。")
    stored_patient_id = str(payload.get("patient_id") or "").strip()
    if stored_patient_id != str(patient_id or "").strip():
        raise ValueError("该对话记录不属于当前患者档案。")
    messages = _normalize_messages(payload.get("messages"))
    if not messages:
        raise ValueError("对话记录中没有可加载的消息。")
    return messages
