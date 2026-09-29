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
from .personal_workspace import PERSONAL_PATIENT_ID
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
    title: str


def conversation_title(messages: Any, fallback: str = "新对话") -> str:
    """Build a short, stable title without sending conversation text elsewhere."""
    normalized = _normalize_messages(messages)
    for preferred_role in ("user", "assistant"):
        for message in normalized:
            if message["role"] != preferred_role:
                continue
            text = re.sub(r"\s+", " ", message["content"]).strip()
            text = re.sub(r"^[#>*_`\-\s]+", "", text).strip()
            if text:
                return text[:36] + ("..." if len(text) > 36 else "")
    return fallback


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
    title: str | None = None,
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
            "updated_at": now.isoformat(timespec="seconds"),
            "patient_id": str(patient_id or "").strip(),
            "title": _normalize_title(title, messages),
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


def _normalize_title(title: Any, messages: Any = None) -> str:
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return conversation_title(messages)
    return text[:80]


def _validated_conversation_path(
    file_name: str,
    storage_dir: str | None,
    patient_id: str | None,
) -> tuple[Path, bool]:
    name = str(file_name or "").strip()
    if Path(name).name != name or not _CONVERSATION_NAME.fullmatch(name):
        raise ValueError("对话记录选择无效，请刷新列表后重试。")
    selected_patient_id = str(patient_id or "").strip()
    expected_tag = _patient_tag(selected_patient_id)
    marker = re.search(r"_p([0-9a-f]{16})_", name)
    item_tag = marker.group(1) if marker else ""
    is_legacy_personal = not item_tag and selected_patient_id == PERSONAL_PATIENT_ID
    if item_tag != expected_tag and not is_legacy_personal:
        raise ValueError("该对话记录不属于当前患者档案。")
    ensure_app_dirs(storage_dir)
    return conversation_dir(storage_dir) / name, is_legacy_personal


def _read_conversation_payload(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            raise FileNotFoundError(path.name)
        if path.stat().st_size > MAX_CONVERSATION_FILE_BYTES:
            raise ValueError("对话记录文件过大，无法在页面中加载。")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("对话记录已不存在，请刷新列表。") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("对话记录文件损坏或无法读取。") from exc
    if not isinstance(payload, dict):
        raise ValueError("对话记录格式无效。")
    return payload


def upsert_conversation(
    messages: list[dict[str, str]],
    storage_dir: str | None = None,
    *,
    file_name: str | None = None,
    retain_limit: int | None = None,
    patient_id: str | None = None,
    title: str | None = None,
) -> Path:
    """Create a thread once, then atomically update that same local thread."""
    if not str(file_name or "").strip():
        return save_conversation(
            messages,
            storage_dir,
            retain_limit=retain_limit,
            patient_id=patient_id,
            title=title,
        )
    with _CONVERSATION_FILE_LOCK:
        path, is_legacy_personal = _validated_conversation_path(
            str(file_name), storage_dir, patient_id
        )
        payload = _read_conversation_payload(path)
        selected_patient_id = str(patient_id or "").strip()
        stored_patient_id = str(payload.get("patient_id") or "").strip()
        if not stored_patient_id and is_legacy_personal:
            stored_patient_id = PERSONAL_PATIENT_ID
        if stored_patient_id != selected_patient_id:
            raise ValueError("该对话记录不属于当前患者档案。")
        normalized_messages = _normalize_messages(messages)
        payload.update(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "title": _normalize_title(title or payload.get("title"), normalized_messages),
                "safety_notice": SAFETY_NOTICE,
                "messages": normalized_messages,
            }
        )
        serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if len(serialized) > MAX_CONVERSATION_FILE_BYTES:
            raise ValueError("对话内容过大，无法保存。请新建对话后再继续。")
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_bytes(serialized)
        tmp_path.replace(path)
        return path


def rename_conversation(
    file_name: str,
    title: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> str:
    with _CONVERSATION_FILE_LOCK:
        path, is_legacy_personal = _validated_conversation_path(file_name, storage_dir, patient_id)
        payload = _read_conversation_payload(path)
        selected_patient_id = str(patient_id or "").strip()
        stored_patient_id = str(payload.get("patient_id") or "").strip()
        if not stored_patient_id and is_legacy_personal:
            stored_patient_id = PERSONAL_PATIENT_ID
        if stored_patient_id != selected_patient_id:
            raise ValueError("该对话记录不属于当前患者档案。")
        new_title = _normalize_title(title, payload.get("messages"))
        payload["title"] = new_title
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if len(serialized) > MAX_CONVERSATION_FILE_BYTES:
            raise ValueError("对话内容过大，无法重命名。")
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_bytes(serialized)
        tmp_path.replace(path)
        return new_title


def delete_conversation(
    file_name: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> None:
    with _CONVERSATION_FILE_LOCK:
        path, is_legacy_personal = _validated_conversation_path(file_name, storage_dir, patient_id)
        payload = _read_conversation_payload(path)
        selected_patient_id = str(patient_id or "").strip()
        stored_patient_id = str(payload.get("patient_id") or "").strip()
        if not stored_patient_id and is_legacy_personal:
            stored_patient_id = PERSONAL_PATIENT_ID
        if stored_patient_id != selected_patient_id:
            raise ValueError("该对话记录不属于当前患者档案。")
        path.unlink()


def load_conversation_title(
    file_name: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> str:
    with _CONVERSATION_FILE_LOCK:
        path, is_legacy_personal = _validated_conversation_path(file_name, storage_dir, patient_id)
        payload = _read_conversation_payload(path)
        selected_patient_id = str(patient_id or "").strip()
        stored_patient_id = str(payload.get("patient_id") or "").strip()
        if not stored_patient_id and is_legacy_personal:
            stored_patient_id = PERSONAL_PATIENT_ID
        if stored_patient_id != selected_patient_id:
            raise ValueError("该对话记录不属于当前患者档案。")
        return _normalize_title(payload.get("title"), payload.get("messages"))


def list_conversations(
    storage_dir: str | None = None,
    *,
    limit: int = MAX_CONVERSATION_LIST_ITEMS,
    patient_id: str | None = None,
) -> list[ConversationEntry]:
    selected_patient_id = str(patient_id or "").strip()
    expected_tag = _patient_tag(selected_patient_id)
    accepts_legacy_personal = selected_patient_id in {"", PERSONAL_PATIENT_ID}
    try:
        max_items = max(1, min(int(limit), MAX_CONVERSATION_LIST_ITEMS))
    except (OverflowError, TypeError, ValueError):
        max_items = MAX_CONVERSATION_LIST_ITEMS
    with _CONVERSATION_FILE_LOCK:
        ensure_app_dirs(storage_dir)
        target_dir = conversation_dir(storage_dir)
        recent: list[tuple[tuple[int, tuple[str, int, str]], str]] = []
        try:
            with os.scandir(target_dir) as iterator:
                for item in iterator:
                    if not _CONVERSATION_NAME.fullmatch(item.name) or not item.is_file(follow_symlinks=False):
                        continue
                    marker = re.search(r"_p([0-9a-f]{16})_", item.name)
                    item_tag = marker.group(1) if marker else ""
                    if item_tag != expected_tag and not (accepts_legacy_personal and not item_tag):
                        continue
                    try:
                        modified_ns = item.stat(follow_symlinks=False).st_mtime_ns
                    except OSError:
                        continue
                    candidate = (
                        (modified_ns, _conversation_order_key(item.name)),
                        item.name,
                    )
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
                    title=_conversation_file_title(target_dir / file_name),
                )
            )
    return entries


def load_conversation(
    file_name: str,
    storage_dir: str | None = None,
    patient_id: str | None = None,
) -> list[dict[str, str]]:
    selected_patient_id = str(patient_id or "").strip()
    with _CONVERSATION_FILE_LOCK:
        path, is_legacy_personal = _validated_conversation_path(
            file_name, storage_dir, patient_id
        )
        payload = _read_conversation_payload(path)
    stored_patient_id = str(payload.get("patient_id") or "").strip()
    if not stored_patient_id and is_legacy_personal:
        stored_patient_id = PERSONAL_PATIENT_ID
    if stored_patient_id != selected_patient_id:
        raise ValueError("该对话记录不属于当前患者档案。")
    messages = _normalize_messages(payload.get("messages"))
    if not messages:
        raise ValueError("对话记录中没有可加载的消息。")
    return messages


def _conversation_file_title(path: Path) -> str:
    try:
        payload = _read_conversation_payload(path)
    except ValueError:
        return "无法读取的对话"
    return _normalize_title(payload.get("title"), payload.get("messages"))
