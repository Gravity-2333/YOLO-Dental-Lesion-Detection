from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .ai_defaults import SAFETY_NOTICE
from .settings_store import conversation_dir, ensure_app_dirs


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


def save_conversation(
    messages: list[dict[str, str]],
    storage_dir: str | None = None,
    *,
    retain_limit: int | None = None,
) -> Path:
    ensure_app_dirs(storage_dir)
    target_dir = conversation_dir(storage_dir)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")  # 微秒级精度防止同秒覆盖
    prefix = "dental_chat_auto" if retain_limit is not None else "dental_chat"
    path = target_dir / f"{prefix}_{stamp}.json"
    # 若极端情况下仍存在同名文件，追加序号
    if path.exists():
        counter = 1
        while path.exists():
            path = target_dir / f"{prefix}_{stamp}_{counter:02d}.json"
            counter += 1
    payload = {
        "created_at": now.isoformat(timespec="seconds"),
        "safety_notice": SAFETY_NOTICE,
        "messages": _normalize_messages(messages),
    }
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    if retain_limit is not None:
        _prune_conversations(target_dir, retain_limit, "dental_chat_auto_*.json")
    return path
