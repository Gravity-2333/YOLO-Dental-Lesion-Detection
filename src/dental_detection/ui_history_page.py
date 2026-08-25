from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .record_formatters import format_history_record
from .record_views import history_choices_from_rows, history_table_html
from .report_center_ui import ReportCenterComponents, build_report_center
from .ui_content import HISTORY_INTRO_HTML


@dataclass(frozen=True, slots=True)
class HistoryPageData:
    patient_choices: list[tuple[str, str]]
    selected_patient_id: str
    storage_dir: str
    initial_history_rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class HistoryComponents:
    patient_select: Any
    refresh_button: Any
    delete_button: Any
    clear_button: Any
    feedback: Any
    history_select: Any
    history_table: Any
    history_detail: Any
    report_center: ReportCenterComponents


def build_history_page(data: HistoryPageData) -> HistoryComponents:
    with gr.Group(elem_classes=["section-card", "case-card"]):
        gr.HTML(HISTORY_INTRO_HTML)
        patient_select = gr.Dropdown(
            label="当前患者档案",
            choices=data.patient_choices,
            value=data.selected_patient_id,
        )
        with gr.Row(elem_classes=["compact-row"]):
            refresh_button = gr.Button(
                "刷新历史",
                elem_classes=["secondary-action", "compact-button"],
            )
            delete_button = gr.Button(
                "删除所选",
                interactive=False,
                elem_classes=["danger-action", "compact-button"],
            )
            clear_button = gr.Button(
                "清空历史",
                interactive=False,
                elem_classes=["danger-action", "compact-button"],
            )
        feedback = gr.Textbox(
            label="历史反馈",
            interactive=False,
            lines=1,
            elem_classes=["inline-feedback"],
        )
        history_select = gr.Dropdown(
            label="检测历史",
            choices=history_choices_from_rows(data.initial_history_rows),
        )
        with gr.Accordion(
            "结构化历史列表",
            open=False,
            elem_classes=["compact-accordion"],
        ):
            history_table = gr.HTML(
                value=history_table_html(data.initial_history_rows),
                elem_classes=["record-table-shell"],
            )
        history_detail = gr.Markdown(
            value=format_history_record(None),
            label="历史详情",
            show_label=True,
            sanitize_html=True,
            line_breaks=True,
            header_links=False,
            buttons=["copy"],
            container=True,
            elem_id="history-detail",
            elem_classes=["record-detail"],
        )
    report_center = build_report_center(
        data.storage_dir,
        data.selected_patient_id,
        load_initial=False,
    )
    return HistoryComponents(
        patient_select=patient_select,
        refresh_button=refresh_button,
        delete_button=delete_button,
        clear_button=clear_button,
        feedback=feedback,
        history_select=history_select,
        history_table=history_table,
        history_detail=history_detail,
        report_center=report_center,
    )
