from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape
import re
from typing import Any
from urllib.parse import urlparse

import gradio as gr

from .ai_detection_context import build_detection_text_context
from .ai_client import normalize_base_url, validate_ai_request
from .conversation_store import (
    ConversationEntry,
    delete_conversation,
    list_conversations,
    load_conversation,
    rename_conversation,
)
from .gradio_files import clear_file_output
from .settings_store import AiSettings


_CHAT_TIME_PREFIX = "chat-time:"
_CHAT_TIME_MARKER = re.compile(
    r'\s*<span class="ai-message-time-marker(?: ai-chat-time-\d{8}T\d{4})?"'
    r'(?: [^>]*)?></span>\s*',
    re.IGNORECASE,
)
_CHAT_TIME_VALUE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$")


def strip_chat_time_marker(content: Any) -> str:
    return _CHAT_TIME_MARKER.sub("", str(content or "")).strip()


def chat_messages_for_display(messages: Any) -> list[dict[str, str]]:
    displayed: list[dict[str, str]] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "assistant")
        content = strip_chat_time_marker(message.get("content", ""))
        metadata = message.get("metadata")
        title = str(metadata.get("title") or "") if isinstance(metadata, dict) else ""
        if title.startswith(_CHAT_TIME_PREFIX):
            match = _CHAT_TIME_VALUE.fullmatch(title.removeprefix(_CHAT_TIME_PREFIX))
            if match:
                year, month, day, hour, minute = match.groups()
                content += (
                    '\n\n<span class="ai-message-time-marker '
                    f'ai-chat-time-{year}{month}{day}T{hour}{minute}"></span>'
                )
        displayed.append({"role": role, "content": content})
    return displayed


@dataclass(frozen=True, slots=True)
class AiChatPageData:
    saved: AiSettings


@dataclass(frozen=True, slots=True)
class AiChatComponents:
    runtime_status: Any
    clear_button: Any
    chatbot: Any
    input: Any
    send_button: Any
    stop_button: Any
    regenerate_button: Any
    suggestion_buttons: tuple[Any, ...]
    conversation_search: Any
    conversation_select: Any
    conversation_load_button: Any
    conversation_refresh_button: Any
    conversation_title: Any
    conversation_rename_button: Any
    conversation_delete_button: Any
    conversation_feedback: Any
    branch_index: Any
    branch_button: Any
    export_path: Any
    export_button: Any
    export_file: Any


def build_ai_runtime_status(
    history: list[dict[str, str]] | None,
    settings: AiSettings,
    batch_state: Any = None,
    selected_name: Any = None,
) -> str:
    detection_context = build_detection_text_context(batch_state, selected_name)
    if detection_context.available:
        context_text = f"已加载 · {detection_context.detection_count} 个检测框"
    else:
        context_text = "尚无当前检测"
    conversation_text = f"{len(history)} 条消息" if history else "尚无对话"
    configured, _, error = validate_ai_request(settings)
    if not settings.enabled:
        configuration_text = "AI 功能未开启"
        state_class = "is-offline"
    elif configured:
        configuration_text = "配置完整"
        state_class = "is-ready"
    else:
        configuration_text = error or "配置不完整"
        state_class = "is-warning"
    normalized_url = normalize_base_url(settings.base_url)
    host = urlparse(normalized_url).hostname or "未配置接口"
    model = str(settings.model or "未配置模型").strip()
    return (
        '<div class="ai-chat-runtime">'
        f'<span class="ai-runtime-state {state_class}"><i></i>{escape(configuration_text)}</span>'
        f'<span><b>上下文</b>{escape(context_text)}</span>'
        f'<span><b>会话</b>{escape(conversation_text)}</span>'
        f'<span><b>模型</b>{escape(model)}</span>'
        f'<span><b>接口</b>{escape(host)}</span>'
        '<span class="ai-runtime-privacy"><b>隐私</b>仅发送检测文字与提问，不含影像</span>'
        "</div>"
    )


def refresh_conversation_history(
    storage_dir: str,
    patient_id: str,
    feedback: str = "",
    query: str = "",
):
    try:
        entries = list_conversations(storage_dir, patient_id=patient_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise gr.Error(f"对话记录读取失败：{exc}") from exc
    query_text = str(query or "").strip().casefold()
    if query_text:
        entries = [entry for entry in entries if query_text in entry.title.casefold()]
    choices = _conversation_choices(entries)
    selected = None
    if feedback:
        message = feedback
    elif query_text:
        message = f"找到 {len(choices)} 条匹配对话。" if choices else "没有匹配的对话。"
    else:
        message = "已加载最近对话列表。" if choices else "暂无本地对话记录。"
    return gr.update(choices=choices, value=selected), message


def search_conversation_history(
    query: str,
    storage_dir: str,
    patient_id: str,
):
    return refresh_conversation_history(storage_dir, patient_id, query=query)


def _conversation_choices(entries: list[ConversationEntry]) -> list[tuple[str, str]]:
    base_labels = [
        f"{entry.title}  ·  {entry.modified_at:%m-%d %H:%M}"
        for entry in entries
    ]
    totals = Counter(base_labels)
    positions: Counter[str] = Counter()
    choices = []
    for entry, base_label in zip(entries, base_labels):
        label = base_label
        if totals[base_label] > 1:
            positions[base_label] += 1
            label = f"{base_label}  {positions[base_label]}/{totals[base_label]}"
        choices.append((label, entry.file_name))
    return choices


def load_conversation_history_item(
    file_name: str,
    storage_dir: str,
    patient_id: str,
):
    if not str(file_name or "").strip():
        raise gr.Error("请先选择一条本地对话记录。")
    try:
        messages = load_conversation(file_name, storage_dir, patient_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise gr.Error(str(exc)) from exc
    return (
        chat_messages_for_display(messages),
        messages,
        "",
        clear_file_output(),
        "",
        "已加载所选对话。",
    )


def rename_conversation_history_item(
    file_name: str,
    title: str,
    storage_dir: str,
    patient_id: str,
    query: str = "",
):
    if not str(file_name or "").strip():
        raise gr.Error("请先选择一条对话。")
    if not str(title or "").strip():
        raise gr.Error("请输入新的对话名称。")
    try:
        new_title = rename_conversation(file_name, title, storage_dir, patient_id)
        selector, _ = refresh_conversation_history(
            storage_dir, patient_id, query=query
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise gr.Error(str(exc)) from exc
    selector["value"] = file_name
    return selector, new_title, f"已重命名为“{new_title}”。"


def delete_conversation_history_item(
    file_name: str,
    storage_dir: str,
    patient_id: str,
    query: str = "",
):
    if not str(file_name or "").strip():
        raise gr.Error("请先选择一条对话。")
    try:
        delete_conversation(file_name, storage_dir, patient_id)
        selector, _ = refresh_conversation_history(
            storage_dir, patient_id, query=query
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise gr.Error(str(exc)) from exc
    return selector, "", "已删除所选本地对话。"


def chat_export_button_state(history: Any):
    return gr.update(interactive=bool(history))


def build_ai_chat_page(data: AiChatPageData) -> AiChatComponents:
    suggestions = (
        "请按优先级说明需要重点复核的位置",
        "用医生视角总结当前检测结果",
        "有哪些影像质量问题会影响判断",
    )
    with gr.Group(elem_classes=["ai-chat-workspace"]):
        with gr.Row(elem_classes=["ai-chat-layout"]):
            with gr.Column(scale=3, min_width=252, elem_classes=["ai-chat-sidebar"]):
                gr.HTML(
                    '<div class="ai-sidebar-heading"><div><span>本地工作区</span>'
                    '<h2>AI 对话</h2></div><span class="ai-private-badge">本机记录</span></div>'
                )
                clear_button = gr.Button(
                    "＋  新建对话",
                    elem_classes=["ai-new-chat-button"],
                )
                conversation_search = gr.Textbox(
                    label="搜索对话",
                    show_label=False,
                    placeholder="搜索最近对话",
                    lines=1,
                    max_lines=1,
                    elem_classes=["ai-conversation-search"],
                )
                with gr.Row(elem_classes=["ai-conversation-heading-row"]):
                    gr.HTML('<div class="ai-sidebar-section-label">最近对话</div>')
                    conversation_refresh_button = gr.Button(
                        "刷新对话",
                        size="sm",
                        elem_classes=["ai-conversation-refresh-button"],
                    )
                conversation_select = gr.Radio(
                    label="最近对话",
                    show_label=False,
                    choices=[],
                    elem_classes=["ai-conversation-list"],
                )
                conversation_load_button = gr.Button(
                    "打开",
                    size="sm",
                    elem_classes=["secondary-action", "ai-conversation-open-action"],
                )
                conversation_title = gr.Textbox(
                    label="对话名称",
                    show_label=False,
                    placeholder="输入名称后重命名",
                    lines=1,
                    max_lines=1,
                    elem_classes=["ai-conversation-title"],
                )
                with gr.Row(
                    elem_classes=["ai-sidebar-actions", "ai-conversation-manage-actions"]
                ):
                    conversation_rename_button = gr.Button(
                        "重命名",
                        size="sm",
                        elem_classes=["secondary-action", "ai-conversation-rename-action"],
                    )
                    conversation_delete_button = gr.Button(
                        "删除",
                        size="sm",
                        elem_classes=["danger-action", "ai-conversation-delete-action"],
                    )
                conversation_feedback = gr.Markdown(
                    "对话记录按患者档案隔离保存在本机。",
                    elem_classes=["ai-sidebar-feedback"],
                )
                branch_index = gr.Textbox(
                    value="",
                    show_label=False,
                    elem_classes=["ai-branch-index"],
                )
                branch_button = gr.Button(
                    "创建分支",
                    elem_classes=["ai-branch-action"],
                )

            gr.HTML(
                '<div class="ai-sidebar-resizer" role="separator" tabindex="0" '
                'aria-label="调整历史记录栏宽度" aria-orientation="vertical" '
                'aria-valuemin="240" aria-valuemax="480" aria-valuenow="300">'
                '<span aria-hidden="true"></span></div>',
                container=False,
            )

            with gr.Column(scale=9, min_width=0, elem_classes=["ai-chat-main"]):
                with gr.Row(elem_classes=["ai-chat-topbar"]):
                    gr.HTML(
                        '<div class="ai-chat-title"><span class="ai-assistant-mark">AI</span>'
                        '<div><h2>牙科辅助分析助手</h2><p>结合当前检测摘要，继续复核与归纳</p></div></div>'
                    )
                    with gr.Row(elem_classes=["ai-chat-top-actions"]):
                        regenerate_button = gr.Button(
                            "重新生成",
                            size="sm",
                            elem_classes=["secondary-action", "ai-regenerate-button"],
                        )
                        export_button = gr.Button(
                            "导出",
                            interactive=False,
                            size="sm",
                            elem_classes=["secondary-action", "ai-export-button"],
                        )
                runtime_status = gr.HTML(build_ai_runtime_status([], data.saved))
                with gr.Row(elem_classes=["ai-prompt-suggestions"]):
                    suggestion_buttons = tuple(
                        gr.Button(
                            suggestion,
                            size="sm",
                            elem_classes=["ai-suggestion-chip"],
                        )
                        for suggestion in suggestions
                    )
                chatbot = gr.Chatbot(
                    label="问答记录",
                    show_label=False,
                    height=510,
                    min_height=420,
                    layout="bubble",
                    editable="user",
                    buttons=None,
                    placeholder=(
                        "完成一次牙片检测后，可询问重点复核位置、检测结果概览，"
                        "或影像质量对判断的影响。"
                    ),
                    elem_classes=["ai-chat-thread", "chat-window"],
                )
                with gr.Row(elem_classes=["ai-composer"]):
                    chat_input = gr.Textbox(
                        label="继续提问",
                        show_label=False,
                        placeholder="向牙科辅助分析助手提问...",
                        lines=2,
                        max_lines=6,
                        autofocus=False,
                        elem_classes=["ai-composer-input"],
                    )
                    with gr.Column(min_width=108, elem_classes=["ai-composer-actions"]):
                        send_button = gr.Button(
                            "发送",
                            variant="primary",
                            elem_classes=["primary-action", "ai-send-button"],
                        )
                        stop_button = gr.Button(
                            "停止",
                            variant="stop",
                            size="sm",
                            elem_classes=["ai-stop-button"],
                        )
                gr.HTML(
                    '<div class="ai-composer-note"><span>Enter 发送 · Shift + Enter 换行</span>'
                    '<span>AI 结果仅供辅助参考，不能替代专业牙科医生诊断</span></div>'
                )
                export_path = gr.Textbox(
                    label="导出路径",
                    interactive=False,
                    visible=False,
                    elem_classes=["path-output"],
                )
                export_file = gr.File(label="导出的对话文件", visible=False)
    return AiChatComponents(
        runtime_status=runtime_status,
        clear_button=clear_button,
        chatbot=chatbot,
        input=chat_input,
        send_button=send_button,
        stop_button=stop_button,
        regenerate_button=regenerate_button,
        suggestion_buttons=suggestion_buttons,
        conversation_search=conversation_search,
        conversation_select=conversation_select,
        conversation_load_button=conversation_load_button,
        conversation_refresh_button=conversation_refresh_button,
        conversation_title=conversation_title,
        conversation_rename_button=conversation_rename_button,
        conversation_delete_button=conversation_delete_button,
        conversation_feedback=conversation_feedback,
        branch_index=branch_index,
        branch_button=branch_button,
        export_path=export_path,
        export_button=export_button,
        export_file=export_file,
    )
