from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .record_formatters import history_record_detail_html
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
    initial_choices = history_choices_from_rows(data.initial_history_rows)
    initial_selected = initial_choices[0][1] if initial_choices else None
    with gr.Group(elem_classes=["record-workspace", "history-workspace"]):
        gr.HTML(HISTORY_INTRO_HTML, elem_classes=["record-workspace-header-host"])

        with gr.Row(elem_classes=["record-patient-bar"], equal_height=True):
            patient_select = gr.Dropdown(
                label="当前患者档案",
                choices=data.patient_choices,
                value=data.selected_patient_id,
                elem_classes=["record-patient-select"],
                scale=1,
            )
            refresh_button = gr.Button(
                "刷新历史",
                elem_classes=["secondary-action", "record-toolbar-button"],
                scale=0,
            )
        feedback = gr.Textbox(
            label="历史反馈",
            interactive=False,
            lines=1,
            show_label=False,
            elem_classes=["inline-feedback", "record-feedback"],
        )

        with gr.Row(elem_classes=["record-review-layout"], equal_height=False):
            with gr.Column(scale=4, min_width=320, elem_classes=["record-library-pane"]):
                gr.HTML(
                    '<div class="history-queue-toolbar">'
                    '<div class="record-pane-heading"><div><span>EXAM REVIEW</span>'
                    '<h3>检查审阅队列</h3></div><p>最近记录优先，选择后在右侧完成审阅。</p></div>'
                    '<div class="history-actions">'
                        '<button type="button" class="history-actions-trigger" '
                        'aria-label="打开历史操作" aria-expanded="false">'
                        '<svg viewBox="0 0 24 24" aria-hidden="true">'
                        '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/>'
                        '<circle cx="12" cy="19" r="1"/></svg></button>'
                        '<div class="history-actions-menu" role="menu" aria-hidden="true">'
                        '<span>历史操作</span>'
                        '<button type="button" data-history-action="delete" role="menuitem">'
                        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2"/>'
                        '<path d="m19 6-1 14H6L5 6M10 11v5M14 11v5"/></svg>'
                        '<span><strong>删除当前记录</strong><small>保留病例与报告</small></span></button>'
                        '<button type="button" data-history-action="clear" role="menuitem">'
                        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>'
                        '<path d="M3 3v5h5"/></svg>'
                        '<span><strong>清空患者历史</strong><small>需要再次确认</small></span></button>'
                    '</div></div></div>',
                    elem_classes=["history-actions-host"],
                )
                history_table = gr.HTML(
                    value=history_table_html(data.initial_history_rows, initial_selected),
                    elem_classes=["record-overview", "history-overview"],
                )
                history_select = gr.Radio(
                    label="检测历史",
                    show_label=False,
                    choices=initial_choices,
                    value=initial_selected,
                    elem_classes=["history-state-proxy"],
                )
                with gr.Row(elem_classes=["history-action-proxies"]):
                    delete_button = gr.Button(
                        "删除所选",
                        interactive=bool(initial_selected),
                        elem_classes=["history-delete-proxy"],
                    )
                    clear_button = gr.Button(
                        "清空历史",
                        interactive=bool(initial_selected),
                        elem_classes=["history-clear-proxy"],
                    )

            with gr.Column(scale=7, min_width=500, elem_classes=["record-detail-pane"]):
                with gr.Row(elem_classes=["record-detail-toolbar"], equal_height=True):
                    gr.HTML(
                        '<div><span>DETECTION REVIEW</span><h3>检查详情</h3></div>',
                        elem_classes=["record-detail-title"],
                    )
                history_detail = gr.HTML(
                    value=history_record_detail_html(None),
                    elem_id="history-detail",
                    elem_classes=["record-detail"],
                )
                report_center = build_report_center(
                    data.storage_dir,
                    data.selected_patient_id,
                    load_initial=False,
                    embedded=True,
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
