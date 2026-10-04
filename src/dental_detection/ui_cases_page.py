from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .record_formatters import case_record_detail_html
from .record_views import case_choices_from_rows, case_table_html
from .ui_content import CASE_INTRO_HTML


@dataclass(frozen=True, slots=True)
class CasesPageData:
    patient_choices: list[tuple[str, str]]
    selected_patient_id: str
    selected_patient_name: str
    selected_patient_reference: str | None
    archived_patient_choices: list[tuple[str, str]]
    initial_case_rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class CasesComponents:
    patient_select: Any
    new_patient_name: Any
    new_patient_reference: Any
    add_patient_button: Any
    edit_patient_name: Any
    edit_patient_reference: Any
    save_patient_button: Any
    archive_patient_button: Any
    archived_patient_select: Any
    restore_patient_button: Any
    patient_feedback: Any
    case_id: Any
    case_note: Any
    save_case_button: Any
    refresh_case_button: Any
    case_feedback: Any
    keyword: Any
    class_filter: Any
    level_filter: Any
    date_from: Any
    date_to: Any
    search_button: Any
    delete_button: Any
    export_button: Any
    case_select: Any
    case_table: Any
    report_file: Any
    report_path: Any
    case_detail: Any


def build_cases_page(data: CasesPageData) -> CasesComponents:
    with gr.Group(elem_classes=["record-workspace", "case-workspace"]):
        gr.HTML(CASE_INTRO_HTML, elem_classes=["record-workspace-header-host"])

        with gr.Row(elem_classes=["record-patient-bar"], equal_height=True):
            patient_select = gr.Dropdown(
                label="当前患者档案",
                choices=data.patient_choices,
                value=data.selected_patient_id,
                elem_classes=["record-patient-select"],
                scale=1,
            )
            refresh_case_button = gr.Button(
                "刷新病例",
                elem_classes=["secondary-action", "record-toolbar-button"],
                scale=0,
            )

        with gr.Accordion(
            "患者档案管理",
            open=False,
            elem_classes=["record-management", "compact-accordion"],
        ):
            with gr.Row(elem_classes=["record-management-grid"]):
                with gr.Column(elem_classes=["record-management-section"]):
                    gr.HTML("<h3>添加档案</h3><p>为本人或家庭成员建立独立记录。</p>")
                    new_patient_name = gr.Textbox(
                        label="档案名称",
                        placeholder="例如：本人、儿童或家人",
                        lines=1,
                        max_lines=1,
                    )
                    new_patient_reference = gr.Textbox(
                        label="档案编号（可选）",
                        placeholder="例如：P-002",
                        lines=1,
                        max_lines=1,
                    )
                    add_patient_button = gr.Button(
                        "添加档案",
                        elem_classes=["secondary-action", "compact-button"],
                    )
                with gr.Column(elem_classes=["record-management-section"]):
                    gr.HTML("<h3>当前档案</h3><p>修改名称或将当前档案归档。</p>")
                    edit_patient_name = gr.Textbox(
                        value=data.selected_patient_name,
                        label="档案名称",
                        lines=1,
                        max_lines=1,
                    )
                    edit_patient_reference = gr.Textbox(
                        value=data.selected_patient_reference,
                        label="档案编号（可选）",
                        lines=1,
                        max_lines=1,
                    )
                    with gr.Row(elem_classes=["record-inline-actions"]):
                        save_patient_button = gr.Button(
                            "保存档案",
                            elem_classes=["secondary-action", "compact-button"],
                        )
                        archive_patient_button = gr.Button(
                            "归档",
                            interactive=False,
                            elem_classes=["danger-action", "compact-button"],
                        )
                with gr.Column(elem_classes=["record-management-section"]):
                    gr.HTML("<h3>归档恢复</h3><p>恢复后重新显示在患者选择器中。</p>")
                    archived_patient_select = gr.Dropdown(
                        label="已归档档案",
                        choices=data.archived_patient_choices,
                        value=(
                            data.archived_patient_choices[0][1]
                            if data.archived_patient_choices
                            else None
                        ),
                    )
                    restore_patient_button = gr.Button(
                        "恢复档案",
                        interactive=bool(data.archived_patient_choices),
                        elem_classes=["secondary-action", "compact-button"],
                    )
            patient_feedback = gr.HTML(elem_classes=["record-management-feedback"])

        with gr.Group(elem_classes=["record-capture-strip"]):
            gr.HTML(
                '<div class="record-strip-heading"><span>NEW CASE</span>'
                '<div><h3>保存当前检测</h3><p>检测完成后补充病例编号和医生备注。</p></div></div>'
            )
            with gr.Row(elem_classes=["record-capture-fields"], equal_height=True):
                case_id = gr.Textbox(
                    label="病例编号 / 备注名称",
                    placeholder="例如：20261002-复查",
                    lines=1,
                    max_lines=1,
                    scale=3,
                )
                case_note = gr.Textbox(
                    label="病例备注",
                    placeholder="主诉、复查说明或医生备注",
                    lines=1,
                    max_lines=3,
                    scale=5,
                )
                save_case_button = gr.Button(
                    "完成检测后可保存",
                    variant="primary",
                    interactive=False,
                    elem_classes=["primary-action", "record-save-button"],
                    scale=0,
                )
            case_feedback = gr.Textbox(
                label="病例反馈",
                interactive=False,
                lines=1,
                show_label=False,
                elem_classes=["inline-feedback", "record-feedback"],
            )

        with gr.Row(elem_classes=["record-review-layout"], equal_height=False):
            with gr.Column(scale=4, min_width=320, elem_classes=["record-library-pane"]):
                gr.HTML(
                    '<div class="record-pane-heading"><div><span>CASE LIBRARY</span>'
                    '<h3>病例档案</h3></div><p>搜索、筛选并选择需要复核的病例。</p></div>'
                )
                keyword = gr.Textbox(
                    label="搜索病例",
                    show_label=False,
                    placeholder="搜索编号、影像、备注或类别",
                    lines=1,
                    max_lines=1,
                    elem_classes=["record-search"],
                )
                with gr.Row(elem_classes=["record-filter-row"]):
                    class_filter = gr.Dropdown(
                        label="类别",
                        choices=["全部", "龋齿", "根尖周病变", "阻生牙", "无检测结果"],
                        value="全部",
                    )
                    level_filter = gr.Dropdown(
                        label="关注等级",
                        choices=["全部", "重点关注", "建议复查", "低置信度参考", "无检测结果"],
                        value="全部",
                    )
                with gr.Accordion(
                    "日期范围",
                    open=False,
                    elem_classes=["record-filter-accordion", "compact-accordion"],
                ):
                    with gr.Row(elem_classes=["record-filter-row"]):
                        date_from = gr.Textbox(
                            label="开始日期",
                            placeholder="YYYY-MM-DD",
                            lines=1,
                            max_lines=1,
                        )
                        date_to = gr.Textbox(
                            label="结束日期",
                            placeholder="YYYY-MM-DD",
                            lines=1,
                            max_lines=1,
                        )
                search_button = gr.Button(
                    "应用筛选",
                    elem_classes=["secondary-action", "record-filter-button"],
                )
                case_table = gr.HTML(
                    value=case_table_html(data.initial_case_rows),
                    elem_classes=["record-overview"],
                )
                case_select = gr.Radio(
                    label="病例列表",
                    show_label=False,
                    choices=case_choices_from_rows(data.initial_case_rows),
                    elem_classes=["record-navigator", "case-navigator"],
                )

            with gr.Column(scale=7, min_width=480, elem_classes=["record-detail-pane"]):
                with gr.Row(elem_classes=["record-detail-toolbar"], equal_height=True):
                    gr.HTML(
                        '<div><span>CASE REVIEW</span><h3>病例详情</h3></div>',
                        elem_classes=["record-detail-title"],
                    )
                    export_button = gr.Button(
                        "导出病例报告",
                        interactive=False,
                        elem_classes=["secondary-action", "record-toolbar-button"],
                    )
                    delete_button = gr.Button(
                        "移入回收站",
                        interactive=False,
                        elem_classes=["danger-action", "record-toolbar-button"],
                    )
                case_detail = gr.HTML(
                    value=case_record_detail_html(None),
                    elem_id="case-detail",
                    elem_classes=["record-detail"],
                )
                report_file = gr.File(
                    label="病例报告 Word",
                    visible=False,
                    elem_classes=["record-download"],
                )
                report_path = gr.HTML(
                    value="",
                    container=False,
                    elem_classes=["export-path-status", "record-path-output"],
                )

    return CasesComponents(
        patient_select=patient_select,
        new_patient_name=new_patient_name,
        new_patient_reference=new_patient_reference,
        add_patient_button=add_patient_button,
        edit_patient_name=edit_patient_name,
        edit_patient_reference=edit_patient_reference,
        save_patient_button=save_patient_button,
        archive_patient_button=archive_patient_button,
        archived_patient_select=archived_patient_select,
        restore_patient_button=restore_patient_button,
        patient_feedback=patient_feedback,
        case_id=case_id,
        case_note=case_note,
        save_case_button=save_case_button,
        refresh_case_button=refresh_case_button,
        case_feedback=case_feedback,
        keyword=keyword,
        class_filter=class_filter,
        level_filter=level_filter,
        date_from=date_from,
        date_to=date_to,
        search_button=search_button,
        delete_button=delete_button,
        export_button=export_button,
        case_select=case_select,
        case_table=case_table,
        report_file=report_file,
        report_path=report_path,
        case_detail=case_detail,
    )
