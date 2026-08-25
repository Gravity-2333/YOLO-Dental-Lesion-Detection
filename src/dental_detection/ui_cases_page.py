from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .record_formatters import format_case_record
from .record_views import case_choices_from_rows, case_table_html
from .ui_content import CASE_INTRO_HTML, section_heading


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
    with gr.Group(elem_classes=["section-card", "case-card"]):
        gr.HTML(CASE_INTRO_HTML)
        patient_select = gr.Dropdown(
            label="当前患者档案",
            choices=data.patient_choices,
            value=data.selected_patient_id,
        )
        with gr.Accordion("添加患者档案", open=False, elem_classes=["compact-accordion"]):
            with gr.Row(elem_classes=["compact-row"]):
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
        with gr.Accordion("管理当前档案", open=False, elem_classes=["compact-accordion"]):
            with gr.Row(elem_classes=["compact-row"]):
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
            with gr.Row(elem_classes=["compact-row"]):
                save_patient_button = gr.Button(
                    "保存档案",
                    elem_classes=["secondary-action", "compact-button"],
                )
                archive_patient_button = gr.Button(
                    "归档当前档案",
                    interactive=False,
                    elem_classes=["secondary-action", "compact-button"],
                )
        with gr.Accordion("恢复已归档档案", open=False, elem_classes=["compact-accordion"]):
            with gr.Row(elem_classes=["compact-row"]):
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
        patient_feedback = gr.HTML()
        with gr.Row(elem_classes=["compact-row"]):
            case_id = gr.Textbox(
                label="病例编号 / 备注名称",
                placeholder="例如：20260602-复查",
                lines=1,
                max_lines=1,
            )
            case_note = gr.Textbox(
                label="病例备注",
                placeholder="可填写主诉、复查说明或医生备注",
                lines=1,
                max_lines=3,
            )
        with gr.Row(elem_classes=["compact-row"]):
            save_case_button = gr.Button(
                "完成检测后可保存",
                variant="primary",
                interactive=False,
                elem_classes=["primary-action", "compact-button"],
            )
            refresh_case_button = gr.Button(
                "刷新记录",
                elem_classes=["secondary-action", "compact-button"],
            )
        case_feedback = gr.Textbox(
            label="病例反馈",
            interactive=False,
            lines=1,
            elem_classes=["inline-feedback"],
        )

    with gr.Group(elem_classes=["section-card", "case-card"]):
        gr.HTML(
            section_heading(
                "已保存病例",
                "选择记录后查看结构化详情；暂无记录时可先完成一次检测并点击保存病例。",
            )
        )
        with gr.Row(elem_classes=["compact-row"]):
            keyword = gr.Textbox(
                label="搜索病例",
                placeholder="病例编号、图片名称、备注、类别或建议",
                lines=1,
                max_lines=1,
            )
            class_filter = gr.Dropdown(
                label="类别筛选",
                choices=["全部", "龋齿", "根尖周病变", "阻生牙", "无检测结果"],
                value="全部",
            )
            level_filter = gr.Dropdown(
                label="关注等级筛选",
                choices=["全部", "重点关注", "建议复查", "低置信度参考", "无检测结果"],
                value="全部",
            )
        with gr.Row(elem_classes=["compact-row"]):
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
        with gr.Row(elem_classes=["compact-row"]):
            search_button = gr.Button(
                "搜索/筛选",
                elem_classes=["secondary-action", "compact-button"],
            )
            delete_button = gr.Button(
                "移入回收站",
                interactive=False,
                elem_classes=["danger-action", "compact-button"],
            )
            export_button = gr.Button(
                "导出病例报告",
                interactive=False,
                elem_classes=["secondary-action", "compact-button"],
            )
        case_select = gr.Dropdown(
            label="已保存病例",
            choices=case_choices_from_rows(data.initial_case_rows),
        )
        with gr.Accordion(
            "结构化病例列表",
            open=False,
            elem_classes=["compact-accordion"],
        ):
            case_table = gr.HTML(
                value=case_table_html(data.initial_case_rows),
                elem_classes=["record-table-shell"],
            )
        report_file = gr.File(label="病例报告 Word", visible=False)
        report_path = gr.Textbox(
            label="病例报告路径",
            interactive=False,
            lines=1,
            max_lines=1,
            elem_classes=["path-output"],
        )
        case_detail = gr.Markdown(
            value=format_case_record(None),
            label="病例详情",
            show_label=True,
            sanitize_html=True,
            line_breaks=True,
            header_links=False,
            buttons=["copy"],
            container=True,
            elem_id="case-detail",
            elem_classes=["record-detail"],
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
