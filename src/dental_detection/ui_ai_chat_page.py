from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import urlparse

import gradio as gr

from .ai_detection_context import build_detection_text_context
from .ai_client import normalize_base_url, validate_ai_request
from .conversation_store import list_conversations, load_conversation
from .gradio_files import clear_file_output
from .settings_store import AiSettings
from .ui_content import AI_CHAT_INTRO_HTML


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
    conversation_select: Any
    conversation_load_button: Any
    conversation_refresh_button: Any
    conversation_feedback: Any
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
    elif configured:
        configuration_text = "配置完整，连接状态尚未测试"
    else:
        configuration_text = error or "配置不完整"
    normalized_url = normalize_base_url(settings.base_url)
    host = urlparse(normalized_url).hostname or "未配置接口"
    model = str(settings.model or "未配置模型").strip()
    return (
        '<div class="ai-context-strip ai-runtime-strip">'
        "<div><strong>检测上下文</strong>"
        f"<span>{escape(context_text)}</span></div>"
        "<div><strong>当前对话</strong>"
        f"<span>{escape(conversation_text)}</span></div>"
        "<div><strong>发送范围</strong>"
        "<span>检测文字与提问，不含影像</span></div>"
        "<div><strong>AI 配置</strong>"
        f"<span>{escape(configuration_text)}</span></div>"
        "<div><strong>接口与模型</strong>"
        f"<span>{escape(host)} · {escape(model)}</span></div>"
        "</div>"
    )


def refresh_conversation_history(
    storage_dir: str,
    patient_id: str,
    feedback: str = "",
):
    try:
        entries = list_conversations(storage_dir, patient_id=patient_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise gr.Error(f"对话记录读取失败：{exc}") from exc
    choices = [
        (
            f"{entry.modified_at:%Y-%m-%d %H:%M:%S} · "
            f"{'自动保存' if entry.auto_saved else '手动导出'}",
            entry.file_name,
        )
        for entry in entries
    ]
    selected = choices[0][1] if choices else None
    message = feedback or ("已加载最近对话列表。" if choices else "暂无本地对话记录。")
    return gr.update(choices=choices, value=selected), message


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
        messages,
        messages,
        "",
        clear_file_output(),
        "",
        "已加载所选对话；继续发送后会保存为新的对话记录。",
    )


def chat_export_button_state(history: Any):
    return gr.update(interactive=bool(history))


def build_ai_chat_page(data: AiChatPageData) -> AiChatComponents:
    with gr.Group(elem_classes=["section-card", "chat-card"]):
        gr.HTML(AI_CHAT_INTRO_HTML)
        runtime_status = gr.HTML(build_ai_runtime_status([], data.saved))
        with gr.Row(elem_classes=["chat-toolbar"]):
            clear_button = gr.Button(
                "新建对话",
                elem_classes=["secondary-action", "compact-button"],
            )
        with gr.Accordion(
            "最近对话",
            open=False,
            elem_classes=["compact-accordion", "conversation-history"],
        ):
            conversation_select = gr.Dropdown(
                label="本地对话记录",
                choices=[],
            )
            with gr.Row(elem_classes=["compact-row", "conversation-history-actions"]):
                conversation_load_button = gr.Button(
                    "加载对话",
                    elem_classes=["secondary-action", "compact-button"],
                )
                conversation_refresh_button = gr.Button(
                    "刷新列表",
                    elem_classes=["secondary-action", "compact-button"],
                )
            conversation_feedback = gr.Textbox(
                label="对话记录反馈",
                interactive=False,
                lines=1,
                elem_classes=["inline-feedback"],
            )
        chatbot = gr.Chatbot(
            label="问答记录",
            show_label=False,
            height=420,
            placeholder="暂无对话。完成检测后，可以继续追问病变位置、可能风险和复查建议。",
            elem_classes=["chat-window"],
        )
        with gr.Row(elem_classes=["chat-input-row"]):
            chat_input = gr.Textbox(
                label="继续提问",
                placeholder="例如：这个结果需要重点复查哪些位置？",
                scale=7,
            )
            send_button = gr.Button(
                "发送",
                variant="primary",
                scale=1,
                elem_classes=["primary-action", "compact-button"],
            )
        with gr.Row(elem_classes=["path-row"]):
            export_path = gr.Textbox(
                label="导出路径",
                interactive=False,
                lines=1,
                max_lines=1,
                scale=8,
                elem_classes=["path-output"],
            )
            export_button = gr.Button(
                "导出对话",
                interactive=False,
                scale=2,
                elem_classes=["secondary-action"],
            )
            export_file = gr.File(label="导出的对话文件", visible=False)
    return AiChatComponents(
        runtime_status=runtime_status,
        clear_button=clear_button,
        chatbot=chatbot,
        input=chat_input,
        send_button=send_button,
        conversation_select=conversation_select,
        conversation_load_button=conversation_load_button,
        conversation_refresh_button=conversation_refresh_button,
        conversation_feedback=conversation_feedback,
        export_path=export_path,
        export_button=export_button,
        export_file=export_file,
    )
