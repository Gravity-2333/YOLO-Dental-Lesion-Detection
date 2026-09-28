from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .ai_defaults import DEFAULT_AI_PROMPT
from .model_files import ADVANCED_MODEL_HINT
from .model_info import legend_html
from .settings_store import AiSettings
from .ui_constants import MODEL_MODE_COMPARE, MODEL_MODE_SINGLE
from .ui_content import (
    AI_INTERFACE_HELP,
    DISPLAY_OPTIONS_HELP,
    MODEL_SELECTION_HELP,
    STORAGE_HELP,
    section_heading,
)


AI_REQUEST_KEYS = (
    "ai_enabled",
    "base_url",
    "ai_model",
    "key_mode",
    "env_api_key",
    "direct_api_key_hidden",
    "direct_api_key_visible",
    "direct_key_visible",
    "save_key",
    "auto_save",
    "storage_dir",
    "custom_prompt",
    "advice_style",
)


@dataclass(frozen=True, slots=True)
class SettingsPageData:
    saved: AiSettings
    primary_model_path: str
    model_cards_html: str
    model_card_choices: list[tuple[str, str]]
    model_choices: list[tuple[str, str]]
    selected_model_choice: str | None
    model_dir: str
    compare_model_path: str
    model_info_markdown: str
    env_api_key: str
    direct_api_key: str


@dataclass(frozen=True, slots=True)
class SettingsComponents:
    enable_compare: Any
    show_summary: Any
    model_cards_view: Any
    model_card_select: Any
    apply_model_card_btn: Any
    settings_model_mode: Any
    show_advanced_models: Any
    model_dir: Any
    open_model_dir_btn: Any
    refresh_model_btn: Any
    model_file_select: Any
    apply_model_btn: Any
    model_apply_target: Any
    primary_model_path: Any
    compare_model_path: Any
    test_model_btn: Any
    model_feedback: Any
    model_info_markdown: Any
    ai_enabled: Any
    advice_style: Any
    ai_group: Any
    ai_model: Any
    base_url: Any
    key_mode: Any
    env_api_key: Any
    direct_api_key_hidden: Any
    direct_api_key_visible: Any
    direct_key_visible: Any
    show_direct_key_btn: Any
    save_key: Any
    custom_prompt: Any
    test_btn: Any
    test_result: Any
    auto_save: Any
    save_history: Any
    history_limit: Any
    storage_dir: Any
    open_storage_btn: Any
    default_storage_btn: Any
    save_settings_btn: Any
    settings_feedback: Any

    def common_input_map(
        self,
        *,
        model_mode: Any,
        patient_id: Any,
        conf: Any,
        iou: Any,
        device_choice: Any,
        use_clahe: Any,
    ) -> dict[str, Any]:
        return {
            "model_mode": model_mode,
            "patient_id": patient_id,
            "primary_model_path": self.primary_model_path,
            "compare_model_path": self.compare_model_path,
            "conf": conf,
            "iou": iou,
            "device_choice": device_choice,
            "use_clahe": use_clahe,
            "enable_compare": self.enable_compare,
            "show_summary": self.show_summary,
            "ai_enabled": self.ai_enabled,
            "base_url": self.base_url,
            "ai_model": self.ai_model,
            "key_mode": self.key_mode,
            "env_api_key": self.env_api_key,
            "direct_api_key_hidden": self.direct_api_key_hidden,
            "direct_api_key_visible": self.direct_api_key_visible,
            "direct_key_visible": self.direct_key_visible,
            "save_key": self.save_key,
            "auto_save": self.auto_save,
            "storage_dir": self.storage_dir,
            "custom_prompt": self.custom_prompt,
            "advice_style": self.advice_style,
            "save_history": self.save_history,
            "history_limit": self.history_limit,
        }

    def ai_request_inputs(self) -> list[Any]:
        return [getattr(self, key) for key in AI_REQUEST_KEYS]


def build_settings_page(data: SettingsPageData) -> SettingsComponents:
    saved = data.saved
    with gr.Group(elem_classes=["settings-sections"]):
        with gr.Accordion("工作台", open=True, elem_classes=["settings-section"]):
            with gr.Group(elem_classes=["settings-card"]):
                gr.HTML(
                    section_heading(
                        "显示选项",
                        "控制主工作台中展示的分析能力。",
                        help_title="显示选项说明",
                        help_text=DISPLAY_OPTIONS_HELP,
                    )
                )
                enable_compare = gr.Checkbox(value=saved.enable_compare, label="允许对比模型模式")
                show_summary = gr.Checkbox(value=saved.show_summary, label="显示参数分析摘要")

        with gr.Accordion("模型与推理", open=False, elem_classes=["settings-section"]):
            with gr.Group(elem_classes=["settings-card"]):
                gr.HTML(
                    section_heading(
                        "模型选择",
                        "选择用于检测的模型。普通使用建议保持默认优化模型。",
                        help_title="模型选择说明",
                        help_text=MODEL_SELECTION_HELP,
                    )
                )
                model_cards_view = gr.HTML(data.model_cards_html)
                model_card_select = gr.Radio(
                    choices=data.model_card_choices,
                    value=(
                        data.primary_model_path
                        if any(data.primary_model_path == value for _, value in data.model_card_choices)
                        else None
                    ),
                    label="模型卡片",
                    elem_classes=["segmented-control"],
                )
                apply_model_card_btn = gr.Button(
                    "使用模型卡片", elem_classes=["secondary-action", "compact-button"]
                )
                settings_model_mode = gr.Radio(
                    choices=[MODEL_MODE_SINGLE, MODEL_MODE_COMPARE],
                    value=saved.model_mode if saved.enable_compare else MODEL_MODE_SINGLE,
                    label="模型模式",
                    elem_classes=["segmented-control"],
                )
                with gr.Accordion("高级模型路径设置", open=False):
                    show_advanced_models = gr.Checkbox(
                        value=False,
                        label="显示高级模型 / 实验权重",
                        info=ADVANCED_MODEL_HINT,
                    )
                    with gr.Row(elem_classes=["path-row", "path-picker-row"]):
                        model_dir = gr.Textbox(
                            value=data.model_dir,
                            label="模型目录",
                            lines=1,
                            max_lines=1,
                            scale=8,
                        )
                        open_model_dir_btn = gr.Button(
                            "...",
                            size="sm",
                            scale=1,
                            elem_id="model-dir-picker",
                            elem_classes=["icon-action"],
                        )
                        refresh_model_btn = gr.Button(
                            "刷新", scale=2, elem_classes=["secondary-action"]
                        )
                    with gr.Row(elem_classes=["model-row"]):
                        model_file_select = gr.Dropdown(
                            choices=data.model_choices,
                            value=data.selected_model_choice,
                            label="目录内模型",
                            scale=8,
                        )
                        apply_model_btn = gr.Button(
                            "使用选中模型", elem_classes=["secondary-action"], scale=2
                        )
                    with gr.Row(elem_classes=["compact-row"]):
                        model_apply_target = gr.Radio(
                            choices=["主模型", "对比模型"],
                            value="主模型",
                            label="填入位置",
                            elem_classes=["segmented-control"],
                        )
                    primary_model_path = gr.Textbox(
                        value=data.primary_model_path,
                        label="主模型路径",
                        lines=1,
                        max_lines=1,
                    )
                    compare_model_path = gr.Textbox(
                        value=data.compare_model_path,
                        label="对比模型路径",
                        lines=1,
                        max_lines=1,
                        visible=saved.enable_compare and saved.model_mode == MODEL_MODE_COMPARE,
                    )
                with gr.Row(elem_classes=["compact-row"]):
                    test_model_btn = gr.Button(
                        "测试模型", elem_classes=["secondary-action", "compact-button"]
                    )
                model_feedback = gr.Textbox(label="模型反馈", interactive=False, lines=2)

        with gr.Accordion("模型说明", open=False, elem_classes=["settings-section"]):
            with gr.Group(elem_classes=["settings-card"]):
                gr.HTML(section_heading("模型说明", "识别类别、输入要求、适用边界与安全声明。"))
                model_info_markdown = gr.Markdown(data.model_info_markdown)
                gr.HTML(legend_html())

        with gr.Accordion("AI 接口", open=False, elem_classes=["settings-section"]):
            with gr.Group(elem_classes=["settings-card"]):
                gr.HTML(
                    section_heading(
                        "AI 建议",
                        "配置检测后的辅助建议与追问能力。",
                        help_title="接口说明",
                        help_text=AI_INTERFACE_HELP,
                    )
                )
                ai_enabled = gr.Checkbox(value=saved.enabled, label="启用 AI 建议与问答")
                advice_style = gr.Dropdown(
                    choices=["简洁版", "医生版", "患者版"],
                    value=saved.advice_style,
                    label="AI 建议风格",
                    elem_classes=["compact-control", "short-select"],
                )
                with gr.Group(visible=saved.enabled, elem_classes=["panel-card"]) as ai_group:
                    with gr.Row(elem_classes=["compact-row"]):
                        ai_model = gr.Textbox(value=saved.model, label="模型")
                        base_url = gr.Textbox(
                            value=saved.base_url,
                            label="Base URL",
                            info="仅支持 OpenAI 兼容 Chat Completions 接口。无路径时自动追加 /v1。",
                        )
                    key_mode = gr.Radio(
                        choices=["环境变量", "直接 Key 值"],
                        value=saved.key_mode,
                        label="API Key 类型",
                        elem_classes=["segmented-control"],
                    )
                    env_api_key = gr.Textbox(
                        value=data.env_api_key,
                        label="环境变量名",
                        placeholder="例如：DEEPSEEK_API_KEY",
                        info="填写环境变量名称。",
                        visible=saved.key_mode == "环境变量",
                    )
                    direct_api_key_hidden = gr.Textbox(
                        value=data.direct_api_key,
                        label="直接 API Key",
                        type="password",
                        placeholder="请输入真实 API Key",
                        info="默认不保存真实 Key。",
                        visible=saved.key_mode == "直接 Key 值",
                    )
                    direct_api_key_visible = gr.Textbox(
                        value=data.direct_api_key,
                        label="直接 API Key",
                        type="text",
                        placeholder="请输入真实 API Key",
                        info="当前为明文显示。",
                        visible=False,
                    )
                    direct_key_visible = gr.State(False)
                    with gr.Row(elem_classes=["compact-row"]):
                        show_direct_key_btn = gr.Button(
                            "显示 Key",
                            visible=saved.key_mode == "直接 Key 值",
                            size="sm",
                            elem_classes=["secondary-action", "compact-button"],
                        )
                        save_key = gr.Checkbox(value=saved.save_api_key, label="保存 API Key 到本地配置")
                    custom_prompt = gr.Textbox(
                        value=saved.custom_prompt or DEFAULT_AI_PROMPT,
                        label="AI 建议 Prompt",
                        lines=7,
                        max_lines=12,
                    )
                    with gr.Row(elem_classes=["compact-row"]):
                        test_btn = gr.Button(
                            "测试接口", elem_classes=["secondary-action", "compact-button"]
                        )
                    test_result = gr.Textbox(label="测试反馈", interactive=False, lines=2)

        with gr.Accordion("存储与隐私", open=False, elem_classes=["settings-section"]):
            with gr.Group(elem_classes=["settings-card"]):
                gr.HTML(
                    section_heading(
                        "存储与隐私",
                        "管理本地记录和数据目录。",
                        help_title="存储说明",
                        help_text=STORAGE_HELP,
                    )
                )
                auto_save = gr.Checkbox(value=saved.auto_save, label="自动保存对话记录")
                save_history = gr.Checkbox(value=saved.save_history, label="自动保存检测历史")
                history_limit = gr.Number(
                    value=saved.history_limit,
                    label="自动记录最多保留数量",
                    info="同时用于检测历史和自动保存的对话记录。",
                    precision=0,
                    minimum=1,
                    maximum=1000,
                )
                with gr.Row(elem_classes=["path-row", "path-picker-row"]):
                    storage_dir = gr.Textbox(
                        value=saved.storage_dir,
                        label="存储目录",
                        lines=1,
                        max_lines=1,
                        scale=8,
                    )
                    open_storage_btn = gr.Button(
                        "...",
                        size="sm",
                        scale=1,
                        elem_id="storage-dir-picker",
                        elem_classes=["icon-action"],
                    )
                    default_storage_btn = gr.Button(
                        "恢复默认", scale=2, elem_classes=["secondary-action"]
                    )

    with gr.Row(elem_classes=["settings-actions"]):
        settings_feedback = gr.HTML(elem_classes=["settings-feedback"])
        save_settings_btn = gr.Button(
            "保存设置", variant="primary", elem_classes=["primary-action", "compact-button"]
        )

    return SettingsComponents(
        enable_compare=enable_compare,
        show_summary=show_summary,
        model_cards_view=model_cards_view,
        model_card_select=model_card_select,
        apply_model_card_btn=apply_model_card_btn,
        settings_model_mode=settings_model_mode,
        show_advanced_models=show_advanced_models,
        model_dir=model_dir,
        open_model_dir_btn=open_model_dir_btn,
        refresh_model_btn=refresh_model_btn,
        model_file_select=model_file_select,
        apply_model_btn=apply_model_btn,
        model_apply_target=model_apply_target,
        primary_model_path=primary_model_path,
        compare_model_path=compare_model_path,
        test_model_btn=test_model_btn,
        model_feedback=model_feedback,
        model_info_markdown=model_info_markdown,
        ai_enabled=ai_enabled,
        advice_style=advice_style,
        ai_group=ai_group,
        ai_model=ai_model,
        base_url=base_url,
        key_mode=key_mode,
        env_api_key=env_api_key,
        direct_api_key_hidden=direct_api_key_hidden,
        direct_api_key_visible=direct_api_key_visible,
        direct_key_visible=direct_key_visible,
        show_direct_key_btn=show_direct_key_btn,
        save_key=save_key,
        custom_prompt=custom_prompt,
        test_btn=test_btn,
        test_result=test_result,
        auto_save=auto_save,
        save_history=save_history,
        history_limit=history_limit,
        storage_dir=storage_dir,
        open_storage_btn=open_storage_btn,
        default_storage_btn=default_storage_btn,
        save_settings_btn=save_settings_btn,
        settings_feedback=settings_feedback,
    )
