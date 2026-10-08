from __future__ import annotations

from dataclasses import replace
import json
import re
from typing import Any

from .ai_client import chat_completion
from .conversation_store import conversation_title
from .settings_store import AiSettings


MAX_TASK_MESSAGES = 6
MAX_TASK_MESSAGE_CHARS = 800


def compact_conversation_context(messages: Any) -> tuple[str, str]:
    normalized: list[tuple[str, str]] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "assistant")
        if role not in {"user", "assistant"}:
            continue
        content = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
        if content:
            normalized.append((role, content[:MAX_TASK_MESSAGE_CHARS]))
    selected = normalized[-MAX_TASK_MESSAGES:]
    prompt = next((content for role, content in reversed(selected) if role == "user"), "")
    labels = {"user": "用户", "assistant": "助手"}
    rendered = "\n".join(f"{labels[role]}：{content}" for role, content in selected)
    return prompt, rendered


def render_task_prompt(template: str, messages: Any) -> str:
    prompt, rendered = compact_conversation_context(messages)
    return str(template or "").replace("{{prompt}}", prompt).replace("{{MESSAGES}}", rendered)


def _task_settings(settings: AiSettings) -> AiSettings:
    model = str(settings.task_model or settings.model).strip()
    return replace(settings, model=model)


def generate_conversation_title(settings: AiSettings, messages: Any) -> str:
    if settings.title_generation_mode != "AI 自动生成":
        return conversation_title(messages)
    content = chat_completion(
        _task_settings(settings),
        [{"role": "user", "content": render_task_prompt(settings.title_generation_prompt, messages)}],
        temperature=settings.task_temperature,
        max_tokens=min(settings.task_max_tokens, 120),
    )
    raw_title = content.strip()
    try:
        parsed = json.loads(raw_title)
        if isinstance(parsed, dict):
            raw_title = str(parsed.get("title") or "")
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw_title)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    raw_title = str(parsed.get("title") or raw_title)
            except json.JSONDecodeError:
                pass
    title = re.sub(r"^(?:标题|对话标题)\s*[:：]\s*", "", raw_title)
    title = re.sub(r"^[\"'“”‘’]+|[\"'“”‘’]+$", "", title).strip()
    title = re.sub(r"\s+", " ", title).strip(" -—：:")
    return title[:36] or conversation_title(messages)


def _followup_candidates(content: str) -> list[str]:
    text = str(content or "").strip()
    candidates: list[Any] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("follow_ups"), list):
            candidates = parsed["follow_ups"]
        elif isinstance(parsed, list):
            candidates = parsed
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    candidates = parsed
            except json.JSONDecodeError:
                pass
    if not candidates:
        candidates = re.split(r"\r?\n", text)
    result: list[str] = []
    for value in candidates:
        question = re.sub(r"^\s*(?:[-*]|\d+[.、)])\s*", "", str(value)).strip()
        question = question.strip('"\'“”‘’ ')
        if question and question not in result:
            result.append(question[:48])
        if len(result) == 3:
            break
    return result


def generate_followup_questions(settings: AiSettings, messages: Any) -> tuple[str, ...]:
    if not settings.followup_generation_enabled:
        return ()
    content = chat_completion(
        _task_settings(settings),
        [{"role": "user", "content": render_task_prompt(settings.followup_generation_prompt, messages)}],
        temperature=settings.task_temperature,
        max_tokens=settings.task_max_tokens,
    )
    questions = _followup_candidates(content)
    return tuple(questions[:3])  # type: ignore[return-value]
