from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import gradio as gr

from .ai_defaults import (
    DEFAULT_AI_PROMPT,
    DEFAULT_FOLLOWUP_GENERATION_PROMPT,
    DEFAULT_TITLE_GENERATION_PROMPT,
)
from .model_files import ADVANCED_MODEL_HINT
from .model_info import legend_html
from .settings_store import AiSettings
from .ui_constants import MODEL_MODE_COMPARE, MODEL_MODE_SINGLE
from .ui_content import (
    AI_INTERFACE_HELP,
    DISPLAY_OPTIONS_HELP,
    MODEL_SELECTION_HELP,
    STORAGE_HELP,
    field_label_with_help_html,
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
    settings_nav: Any
    settings_panes: tuple[Any, ...]
    enable_compare: Any
    show_summary: Any
    magnifier_enabled: Any
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
    title_generation_mode: Any
    title_generation_prompt: Any
    followup_generation_enabled: Any
    followup_generation_prompt: Any
    keep_followup_prompts: Any
    followup_click_action: Any
    task_model: Any
    task_temperature: Any
    task_max_tokens: Any
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


@contextmanager
def advanced_settings():
    with gr.Accordion("高级", open=False, elem_classes=["settings-advanced"]):
        with gr.Column(elem_classes=["settings-advanced-content"]):
            yield


def settings_page_heading(title: str, description: str) -> None:
    gr.HTML(
        f'<div class="settings-page-heading"><h2>{title}</h2><p>{description}</p></div>',
        elem_classes=["settings-page-heading-host"],
    )


def build_settings_page(data: SettingsPageData) -> SettingsComponents:
    saved = data.saved
    with gr.Row(elem_classes=["settings-nav-shell"], equal_height=False):
        settings_nav = gr.Radio(
            choices=["工作台", "模型", "AI", "自动化", "存储"],
            value="工作台",
            label="设置栏目",
            show_label=False,
            elem_classes=["settings-nav-control"],
            scale=0,
            min_width=210,
        )
        with gr.Group(visible=True, elem_classes=["settings-pane-host"]) as workbench_settings_pane:
            with gr.Column(elem_classes=["settings-pane"]):
                settings_page_heading("工作台", "调整检测工作区默认展示的能力。")
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
                    gr.HTML(
                        section_heading(
                            "显示选项",
                            "控制主工作台中展示的分析能力。",
                            help_title="显示选项说明",
                            help_text=DISPLAY_OPTIONS_HELP,
                        )
                    )
                    enable_compare = gr.Checkbox(
                        value=saved.enable_compare,
                        label="允许对比模型模式",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    show_summary = gr.Checkbox(
                        value=saved.show_summary,
                        label="显示参数分析摘要",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    magnifier_enabled = gr.Checkbox(
                        value=saved.magnifier_enabled,
                        label="开启检测图悬停放大镜",
                        info="鼠标移入检测结果时，在指针右上方显示局部放大图。",
                        elem_id="magnifier-enabled-setting",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )

        with gr.Group(visible=False, elem_classes=["settings-pane-host"]) as model_settings_pane:
            with gr.Column(elem_classes=["settings-pane"]):
                settings_page_heading("模型与推理", "选择临床辅助筛查使用的权重和运行模式。")
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
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
                        elem_classes=["settings-control-surface", "settings-card-picker"],
                    )
                    with gr.Row(elem_classes=["settings-command-row"]):
                        apply_model_card_btn = gr.Button(
                            "使用模型卡片",
                            elem_classes=["secondary-action", "settings-command-button"],
                        )
                    settings_model_mode = gr.Radio(
                        choices=[MODEL_MODE_SINGLE, MODEL_MODE_COMPARE],
                        value=saved.model_mode if saved.enable_compare else MODEL_MODE_SINGLE,
                        label="模型模式",
                        elem_classes=[
                            "settings-control-surface",
                            "segmented-control",
                            "settings-mode-control",
                        ],
                    )
                    with advanced_settings():
                        show_advanced_models = gr.Checkbox(
                            value=False,
                            label="显示高级模型 / 实验权重",
                            info=ADVANCED_MODEL_HINT,
                            elem_classes=["settings-control-surface", "settings-toggle-row"],
                        )
                        with gr.Row(
                            elem_classes=["path-row", "path-picker-row", "settings-path-row"]
                        ):
                            model_dir = gr.Textbox(
                                value=data.model_dir,
                                label="模型目录",
                                lines=1,
                                max_lines=1,
                                scale=8,
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-text-control",
                                    "settings-path-field",
                                ],
                            )
                            open_model_dir_btn = gr.Button(
                                "浏览",
                                size="sm",
                                scale=1,
                                elem_id="model-dir-picker",
                                elem_classes=[
                                    "secondary-action",
                                    "settings-control-surface",
                                    "settings-inline-button",
                                ],
                            )
                            refresh_model_btn = gr.Button(
                                "刷新",
                                scale=2,
                                elem_classes=[
                                    "secondary-action",
                                    "settings-control-surface",
                                    "settings-inline-button",
                                ],
                            )
                        with gr.Row(elem_classes=["model-row", "settings-model-file-row"]):
                            model_file_select = gr.Dropdown(
                                choices=data.model_choices,
                                value=data.selected_model_choice,
                                label="目录内模型",
                                scale=8,
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-select-control",
                                ],
                            )
                            apply_model_btn = gr.Button(
                                "使用选中模型",
                                elem_classes=[
                                    "secondary-action",
                                    "settings-control-surface",
                                    "settings-inline-button",
                                ],
                                scale=2,
                            )
                        model_apply_target = gr.Radio(
                            choices=["主模型", "对比模型"], value="主模型", label="填入位置",
                            elem_classes=["settings-control-surface", "segmented-control"],
                        )
                        primary_model_path = gr.Textbox(
                            value=data.primary_model_path,
                            label="主模型路径",
                            lines=1,
                            max_lines=1,
                            elem_classes=[
                                "settings-control-surface",
                                "settings-text-control",
                            ],
                        )
                        compare_model_path = gr.Textbox(
                            value=data.compare_model_path,
                            label="对比模型路径",
                            lines=1,
                            max_lines=1,
                            visible=saved.enable_compare and saved.model_mode == MODEL_MODE_COMPARE,
                            elem_classes=[
                                "settings-control-surface",
                                "settings-text-control",
                            ],
                        )
                    with gr.Row(elem_classes=["settings-test-row"], equal_height=True):
                        test_model_btn = gr.Button(
                            "测试模型",
                            elem_classes=["secondary-action", "settings-command-button"],
                            scale=0,
                        )
                        model_feedback = gr.Textbox(
                            label="模型反馈",
                            interactive=False,
                            lines=1,
                            max_lines=2,
                            scale=1,
                            elem_classes=["settings-feedback-field"],
                        )
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
                    gr.HTML(section_heading("模型说明", "识别类别、输入要求、适用边界与安全声明。"))
                    model_info_markdown = gr.Markdown(data.model_info_markdown)
                    gr.HTML(legend_html())

        with gr.Group(visible=False, elem_classes=["settings-pane-host"]) as ai_settings_pane:
            with gr.Column(elem_classes=["settings-pane"]):
                settings_page_heading("AI 接口", "配置建议生成、问答模型和接口凭据。")
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
                    gr.HTML(
                        section_heading(
                            "AI 建议",
                            "配置检测后的辅助建议与追问能力。",
                            help_title="接口说明",
                            help_text=AI_INTERFACE_HELP,
                        )
                    )
                    ai_enabled = gr.Checkbox(
                        value=saved.enabled,
                        label="启用 AI 建议与问答",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    with gr.Group(visible=saved.enabled, elem_classes=["settings-ai-content"]) as ai_group:
                        advice_style = gr.Dropdown(
                            choices=["简洁版", "医生版", "患者版"],
                            value=saved.advice_style,
                            label="AI 建议风格",
                            elem_classes=[
                                "settings-control-surface",
                                "settings-row-control",
                                "settings-select-control",
                            ],
                        )
                        with advanced_settings():
                            with gr.Group(elem_classes=["settings-inner-group"]):
                                custom_prompt = gr.Textbox(
                                    value=saved.custom_prompt or DEFAULT_AI_PROMPT,
                                    label="AI 建议 Prompt",
                                    lines=7,
                                    max_lines=12,
                                    elem_classes=[
                                        "settings-control-surface",
                                        "settings-prompt-control",
                                    ],
                                )
                            with gr.Row(elem_classes=["settings-inline-fields"]):
                                ai_model = gr.Textbox(
                                    value=saved.model,
                                    label="对话模型",
                                    elem_classes=[
                                        "settings-control-surface",
                                        "settings-text-control",
                                    ],
                                )
                                with gr.Column(elem_classes=["settings-field-with-help"]):
                                    gr.HTML(
                                        field_label_with_help_html(
                                            "Base URL",
                                            "Base URL 说明",
                                            "仅支持 OpenAI 兼容 Chat Completions 接口。无路径时自动追加 /v1。",
                                        ),
                                        elem_classes=["settings-field-help-host"],
                                    )
                                    base_url = gr.Textbox(
                                        value=saved.base_url,
                                        label="Base URL",
                                        show_label=False,
                                        elem_classes=[
                                            "settings-control-surface",
                                            "settings-text-control",
                                        ],
                                    )
                            key_mode = gr.Radio(
                                choices=["环境变量", "直接 Key 值"],
                                value=saved.key_mode,
                                label="API Key 类型",
                                elem_classes=["settings-control-surface", "segmented-control"],
                            )
                            env_api_key = gr.Textbox(
                                value=data.env_api_key,
                                label="环境变量名",
                                placeholder="例如：DEEPSEEK_API_KEY",
                                info="填写环境变量名称。",
                                visible=saved.key_mode == "环境变量",
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-text-control",
                                ],
                            )
                            direct_api_key_hidden = gr.Textbox(
                                value=data.direct_api_key,
                                label="直接 API Key",
                                type="password",
                                placeholder="请输入真实 API Key",
                                info="默认不保存真实 Key。",
                                visible=saved.key_mode == "直接 Key 值",
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-text-control",
                                ],
                            )
                            direct_api_key_visible = gr.Textbox(
                                value=data.direct_api_key,
                                label="直接 API Key",
                                type="text",
                                placeholder="请输入真实 API Key",
                                info="当前为明文显示。",
                                visible=False,
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-text-control",
                                ],
                            )
                            direct_key_visible = gr.State(False)
                            with gr.Row(elem_classes=["settings-key-row"], equal_height=True):
                                save_key = gr.Checkbox(
                                    value=saved.save_api_key,
                                    label="保存 API Key 到本地配置",
                                    scale=1,
                                    elem_classes=[
                                        "settings-control-surface",
                                        "settings-toggle-row",
                                    ],
                                )
                                show_direct_key_btn = gr.Button(
                                    "显示 Key", visible=saved.key_mode == "直接 Key 值", size="sm",
                                    elem_classes=["secondary-action", "settings-command-button"],
                                    scale=0,
                                )
                            with gr.Row(elem_classes=["settings-command-row"]):
                                test_btn = gr.Button(
                                    "测试接口",
                                    elem_classes=["secondary-action", "settings-command-button"],
                                )
                            test_result = gr.Textbox(
                                label="测试反馈",
                                interactive=False,
                                lines=1,
                                max_lines=2,
                                elem_classes=["settings-feedback-field"],
                            )

        with gr.Group(visible=False, elem_classes=["settings-pane-host"]) as automation_settings_pane:
            with gr.Column(elem_classes=["settings-pane"]):
                settings_page_heading("对话自动化", "控制标题、后续问题及其交互方式。")
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
                    gr.HTML(
                        section_heading(
                            "对话自动化",
                            "控制新对话标题与下一步追问建议。任务只读取当前对话文字，不读取牙片。",
                        )
                    )
                    title_generation_mode = gr.Radio(
                        choices=["本地规则", "AI 自动生成"],
                        value=saved.title_generation_mode,
                        label="对话标题",
                        elem_classes=["settings-control-surface", "segmented-control"],
                    )
                    followup_generation_enabled = gr.Checkbox(
                        value=saved.followup_generation_enabled,
                        label="每次回复后生成后续问题建议",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    keep_followup_prompts = gr.Checkbox(
                        value=saved.keep_followup_prompts,
                        label="保留历史回复下的后续问题",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    followup_click_action = gr.Radio(
                        choices=["填入输入框", "直接发送"],
                        value=saved.followup_click_action,
                        label="点击后续问题",
                        elem_classes=[
                            "segmented-control",
                            "settings-inline-choice",
                            "settings-followup-click-action",
                            "settings-control-surface",
                        ],
                    )
                    with advanced_settings():
                        with gr.Group(elem_classes=["settings-option-group", "settings-inner-group"]):
                            title_generation_prompt = gr.Textbox(
                                value=saved.title_generation_prompt or DEFAULT_TITLE_GENERATION_PROMPT,
                                label="标题生成 Prompt",
                                lines=5,
                                max_lines=10,
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-prompt-control",
                                ],
                            )
                        with gr.Group(elem_classes=["settings-option-group", "settings-inner-group"]):
                            followup_generation_prompt = gr.Textbox(
                                value=saved.followup_generation_prompt or DEFAULT_FOLLOWUP_GENERATION_PROMPT,
                                label="后续问题生成 Prompt",
                                lines=6,
                                max_lines=12,
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-prompt-control",
                                ],
                            )
                        with gr.Group(elem_classes=["settings-option-group", "settings-inner-group"]):
                            task_model = gr.Textbox(
                                value=saved.task_model,
                                label="任务模型",
                                placeholder="留空时使用当前对话模型",
                                elem_classes=[
                                    "settings-control-surface",
                                    "settings-text-control",
                                ],
                            )
                            with gr.Row(elem_classes=["settings-inline-fields"]):
                                task_temperature = gr.Number(
                                    value=saved.task_temperature,
                                    label="温度",
                                    minimum=0,
                                    maximum=2,
                                    step=0.1,
                                    elem_classes=[
                                        "settings-control-surface",
                                        "settings-number-control",
                                    ],
                                )
                                task_max_tokens = gr.Number(
                                    value=saved.task_max_tokens,
                                    label="最大输出 Token",
                                    minimum=32,
                                    maximum=800,
                                    precision=0,
                                    elem_classes=[
                                        "settings-control-surface",
                                        "settings-number-control",
                                    ],
                                )

        with gr.Group(visible=False, elem_classes=["settings-pane-host"]) as storage_settings_pane:
            with gr.Column(elem_classes=["settings-pane"]):
                settings_page_heading("存储与隐私", "管理本地记录、保留数量和数据目录。")
                with gr.Group(elem_classes=["settings-card", "settings-option-group"]):
                    gr.HTML(
                        section_heading(
                            "存储与隐私",
                            "管理本地记录和数据目录。",
                            help_title="存储说明",
                            help_text=STORAGE_HELP,
                        )
                    )
                    auto_save = gr.Checkbox(
                        value=saved.auto_save,
                        label="自动保存对话记录",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    save_history = gr.Checkbox(
                        value=saved.save_history,
                        label="自动保存检测历史",
                        elem_classes=["settings-control-surface", "settings-toggle-row"],
                    )
                    history_limit = gr.Number(
                        value=saved.history_limit,
                        label="自动记录最多保留数量",
                        info="同时用于检测历史和自动保存的对话记录。",
                        precision=0,
                        minimum=1,
                        maximum=1000,
                        elem_classes=[
                            "settings-control-surface",
                            "settings-row-control",
                            "settings-number-control",
                        ],
                    )
                    with gr.Row(
                        elem_classes=["path-row", "path-picker-row", "settings-path-row"]
                    ):
                        storage_dir = gr.Textbox(
                            value=saved.storage_dir,
                            label="存储目录",
                            lines=1,
                            max_lines=1,
                            scale=8,
                            elem_classes=[
                                "settings-control-surface",
                                "settings-text-control",
                                "settings-path-field",
                            ],
                        )
                        open_storage_btn = gr.Button(
                            "浏览",
                            size="sm",
                            scale=1,
                            elem_id="storage-dir-picker",
                            elem_classes=[
                                "secondary-action",
                                "settings-control-surface",
                                "settings-inline-button",
                            ],
                        )
                        default_storage_btn = gr.Button(
                            "恢复默认",
                            scale=2,
                            elem_classes=[
                                "secondary-action",
                                "settings-control-surface",
                                "settings-inline-button",
                            ],
                        )

    with gr.Row(elem_classes=["settings-actions"]):
        settings_feedback = gr.HTML(elem_classes=["settings-feedback"])
        save_settings_btn = gr.Button(
            "保存设置", variant="primary", elem_classes=["primary-action", "compact-button"]
        )

    return SettingsComponents(
        settings_nav=settings_nav,
        settings_panes=(
            workbench_settings_pane,
            model_settings_pane,
            ai_settings_pane,
            automation_settings_pane,
            storage_settings_pane,
        ),
        enable_compare=enable_compare,
        show_summary=show_summary,
        magnifier_enabled=magnifier_enabled,
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
        title_generation_mode=title_generation_mode,
        title_generation_prompt=title_generation_prompt,
        followup_generation_enabled=followup_generation_enabled,
        followup_generation_prompt=followup_generation_prompt,
        keep_followup_prompts=keep_followup_prompts,
        followup_click_action=followup_click_action,
        task_model=task_model,
        task_temperature=task_temperature,
        task_max_tokens=task_max_tokens,
        auto_save=auto_save,
        save_history=save_history,
        history_limit=history_limit,
        storage_dir=storage_dir,
        open_storage_btn=open_storage_btn,
        default_storage_btn=default_storage_btn,
        save_settings_btn=save_settings_btn,
        settings_feedback=settings_feedback,
    )
