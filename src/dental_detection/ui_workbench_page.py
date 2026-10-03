from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from .model_info import legend_html
from .settings_store import AiSettings
from .ui_constants import (
    BATCH_FILE_LIMIT,
    DETECTION_TABLE_COLUMNS,
    MODEL_MODE_COMPARE,
    MODEL_MODE_SINGLE,
)
from .ui_content import section_heading


@dataclass(frozen=True, slots=True)
class WorkbenchPageData:
    saved: AiSettings
    model_status_html: str
    patient_choices: list[tuple[str, str]]
    selected_patient_id: str
    example_choices: list[tuple[str, str]]
    device_choices: list[str | tuple[str, str]]
    default_device_choice: str
    initial_detection_table: Any
    magnifier_enabled: bool = True


@dataclass(frozen=True, slots=True)
class WorkbenchComponents:
    workbench_model_status: Any
    patient_select: Any
    clear_session_btn: Any
    image: Any
    run_btn: Any
    example_select: Any
    load_example_btn: Any
    example_info: Any
    batch_files: Any
    batch_btn: Any
    batch_select: Any
    export_batch_btn: Any
    export_batch_word_btn: Any
    batch_export_file: Any
    batch_word_file: Any
    batch_export_path: Any
    batch_word_path: Any
    batch_overview: Any
    model_mode: Any
    model_mode_feedback: Any
    device_choice: Any
    conf: Any
    iou: Any
    use_clahe: Any
    original_output: Any
    model_input_output: Any
    result_output: Any
    comparison_section: Any
    comparison_view: Any
    result_image_path: Any
    download_result_btn: Any
    result_image_file: Any
    visible_class_filter: Any
    det_table: Any
    advice_box: Any
    quality_box: Any
    summary: Any
    report_export_menu_btn: Any
    report_export_status: Any
    word_report_path: Any
    export_word_btn: Any
    open_word_report_dir_btn: Any
    word_report_file: Any
    report_path: Any
    export_report_btn: Any
    open_report_dir_btn: Any
    report_file: Any

    def common_input_map(self, settings: Any) -> dict[str, Any]:
        return settings.common_input_map(
            model_mode=self.model_mode,
            patient_id=self.patient_select,
            conf=self.conf,
            iou=self.iou,
            device_choice=self.device_choice,
            use_clahe=self.use_clahe,
        )


def analysis_button_state(value: Any):
    if value is None:
        available = False
    elif isinstance(value, (list, tuple, set, dict)):
        available = bool(value)
    else:
        available = True
    return gr.update(interactive=available)


def build_workbench_page(data: WorkbenchPageData) -> WorkbenchComponents:
    with gr.Group(elem_classes=["section-card", "guide-card", "model-status-card"]):
        workbench_model_status = gr.HTML(data.model_status_html)

    with gr.Row(elem_classes=["workbench-patient-bar"]):
        with gr.Column(elem_classes=["patient-control-group"]):
            gr.HTML('<div class="patient-control-label">当前患者档案</div>', container=False)
            with gr.Row(elem_classes=["patient-control-row"]):
                patient_select = gr.Dropdown(
                    label="当前患者档案",
                    show_label=False,
                    choices=data.patient_choices,
                    value=data.selected_patient_id,
                    elem_classes=["compact-control"],
                )
                clear_session_btn = gr.Button(
                    "清空会话",
                    elem_classes=["secondary-action", "compact-button"],
                )

    with gr.Row(elem_classes=["workbench-grid"]):
        with gr.Column(scale=4, elem_classes=["control-panel"]):
            with gr.Group(elem_classes=["section-card", "upload-card"]):
                with gr.Tabs(elem_classes=["sub-tabs"]):
                    with gr.Tab("单张分析"):
                        gr.HTML(section_heading("上传影像", "请上传牙科影像，或选择真实测试集样本体验流程。"))
                        image = gr.Image(
                            type="pil",
                            label="上传牙科影像",
                            show_label=False,
                            height=280,
                            sources=["upload", "clipboard"],
                            placeholder="拖拽牙科影像到此处\n支持常见图片格式",
                            elem_classes=["upload-input"],
                        )
                        run_btn = gr.Button(
                            "开始分析",
                            variant="primary",
                            interactive=False,
                            elem_classes=["primary-action"],
                        )
                        with gr.Accordion("真实牙片示例", open=False):
                            example_select = gr.Dropdown(
                                label="选择示例",
                                choices=data.example_choices,
                                value=None,
                            )
                            load_example_btn = gr.Button(
                                "加载示例",
                                elem_classes=["secondary-action", "compact-button"],
                            )
                            example_info = gr.Textbox(
                                label="示例说明",
                                value="",
                                interactive=False,
                                lines=2,
                            )

                    with gr.Tab("批量分析"):
                        gr.HTML(
                            section_heading(
                                "批量上传",
                                f"按当前模型模式逐张检测，单次最多 {BATCH_FILE_LIMIT} 张，完成后可统一导出。",
                            )
                        )
                        batch_files = gr.File(
                            label="批量上传图片",
                            show_label=False,
                            file_count="multiple",
                            file_types=[".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"],
                            elem_classes=["upload-input"],
                        )
                        batch_btn = gr.Button(
                            "批量分析",
                            variant="primary",
                            interactive=False,
                            elem_classes=["primary-action"],
                        )
                        batch_select = gr.Dropdown(label="查看图片", choices=[])
                        with gr.Row(elem_classes=["compact-row"]):
                            export_batch_btn = gr.Button(
                                "导出批量结果",
                                interactive=False,
                                elem_classes=["secondary-action"],
                            )
                            export_batch_word_btn = gr.Button(
                                "导出批量 Word",
                                interactive=False,
                                elem_classes=["secondary-action"],
                            )
                            batch_export_file = gr.File(label="批量结果 ZIP", visible=False)
                            batch_word_file = gr.File(label="批量 Word 报告", visible=False)
                        batch_export_path = gr.Textbox(
                            label="批量导出路径",
                            interactive=False,
                            lines=1,
                            max_lines=1,
                            elem_classes=["path-output"],
                        )
                        batch_word_path = gr.Textbox(
                            label="批量 Word 报告路径",
                            interactive=False,
                            lines=1,
                            max_lines=1,
                            elem_classes=["path-output"],
                        )
                        batch_overview = gr.HTML(
                            value="",
                            container=False,
                            elem_classes=["batch-overview-host"],
                        )

            with gr.Group(elem_classes=["section-card", "panel-card"]):
                gr.HTML(
                    section_heading(
                        "检测设置",
                        "选择模式和运行设备。",
                    )
                )
                model_mode = gr.Radio(
                    choices=[MODEL_MODE_SINGLE, MODEL_MODE_COMPARE],
                    value=data.saved.model_mode if data.saved.enable_compare else MODEL_MODE_SINGLE,
                    label="模型模式",
                    elem_classes=["segmented-control"],
                )
                model_mode_feedback = gr.HTML(value="", visible=False, container=False)
                if len(data.device_choices) > 2:
                    device_choice = gr.Dropdown(
                        choices=data.device_choices,
                        value=data.default_device_choice,
                        label="推理设备",
                        elem_classes=["compact-control"],
                    )
                else:
                    device_choice = gr.Radio(
                        choices=data.device_choices,
                        value=data.default_device_choice,
                        label="推理设备",
                        elem_classes=["segmented-control"],
                    )
                with gr.Accordion("高级参数", open=False):
                    with gr.Row(elem_classes=["compact-row"]):
                        conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度")
                        iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU")
                    use_clahe = gr.Checkbox(
                        value=False,
                        label="CLAHE 增强",
                        info="适合低对比度牙片，默认关闭。",
                    )

        with gr.Column(scale=7, elem_classes=["result-panel"]):
            with gr.Group(elem_classes=["image-grid", "clinical-viewer"]):
                with gr.Tabs(elem_classes=["result-view-tabs"]):
                    with gr.Tab("检测结果"):
                        gr.HTML('<div class="image-title">AI 检测结果</div>')
                        with gr.Group(elem_classes=["result-image-stage"]):
                            gr.HTML(
                                (
                                    '<span class="magnifier-runtime-setting" '
                                    f'data-enabled="{str(data.magnifier_enabled).lower()}" hidden></span>'
                                ),
                                container=False,
                            )
                            result_output = gr.Image(
                                type="pil",
                                label="检测结果",
                                show_label=False,
                                height=470,
                                placeholder="完成检测后显示",
                                elem_classes=["result-card", "primary-result-card"],
                            )
                            gr.HTML(
                                legend_html(compact=True),
                                container=False,
                                elem_classes=["result-legend-overlay-host"],
                            )
                    with gr.Tab("滑动对比"):
                        with gr.Group(visible=False, elem_classes=["comparison-results-section"]) as comparison_section:
                            comparison_view = gr.HTML(
                                value="",
                                container=False,
                                elem_classes=["comparison-view-host"],
                            )
                    with gr.Tab("原始影像"):
                        gr.HTML('<div class="image-title">原始影像</div>')
                        original_output = gr.Image(
                            type="pil",
                            label="原图",
                            show_label=False,
                            height=470,
                            placeholder="等待上传",
                            elem_classes=["result-card"],
                        )
                    with gr.Tab("模型输入"):
                        gr.HTML('<div class="image-title">模型输入</div>')
                        model_input_output = gr.Image(
                            type="pil",
                            label="模型输入",
                            show_label=False,
                            height=470,
                            placeholder="完成检测后显示",
                            elem_classes=["result-card"],
                        )

            with gr.Group(elem_classes=["report-export-dock"]):
                report_export_menu_btn = gr.Button(
                    "导出",
                    interactive=False,
                    elem_classes=["report-export-menu-trigger"],
                )
                with gr.Group(elem_classes=["report-export-popover"]):
                    gr.HTML(
                        '<div class="report-export-popover-heading">'
                        '<strong>导出当前结果</strong>'
                        '<span>选择导出内容</span>'
                        '</div>',
                        container=False,
                    )
                    result_image_path = gr.State("")
                    word_report_path = gr.State("")
                    report_path = gr.State("")
                    with gr.Group(elem_classes=["report-export-choice"]):
                        export_word_btn = gr.Button(
                            "导出 Word 报告",
                            interactive=False,
                            elem_classes=["report-export-option", "report-export-option-word"],
                        )
                        with gr.Row(elem_classes=["report-export-choice-actions"]):
                            open_word_report_dir_btn = gr.Button(
                                "打开位置",
                                visible=False,
                                elem_classes=["report-export-subaction", "open-location-action"],
                            )
                            word_report_file = gr.DownloadButton(
                                "下载 Word",
                                visible=False,
                                elem_classes=["report-export-subaction", "download-action"],
                            )
                    with gr.Group(elem_classes=["report-export-choice"]):
                        export_report_btn = gr.Button(
                            "导出 ZIP 数据包",
                            interactive=False,
                            elem_classes=["report-export-option", "report-export-option-zip"],
                        )
                        with gr.Row(elem_classes=["report-export-choice-actions"]):
                            open_report_dir_btn = gr.Button(
                                "打开位置",
                                visible=False,
                                elem_classes=["report-export-subaction", "open-location-action"],
                            )
                            report_file = gr.DownloadButton(
                                "下载 ZIP",
                                visible=False,
                                elem_classes=["report-export-subaction", "download-action"],
                            )
                    with gr.Group(elem_classes=["report-export-choice"]):
                        download_result_btn = gr.Button(
                            "下载结果图片",
                            interactive=False,
                            elem_classes=["report-export-option", "report-export-option-image"],
                        )
                        result_image_file = gr.File(label="检测结果图 PNG", visible=False)
                report_export_status = gr.HTML(
                    "",
                    container=False,
                    elem_classes=["report-export-status"],
                )

            with gr.Row(elem_classes=["insight-grid"]):
                advice_box = gr.Textbox(
                    label="牙齿辅助建议",
                    lines=7,
                    interactive=False,
                    elem_classes=["panel-card"],
                )
                quality_box = gr.Textbox(
                    value="等待上传图像",
                    label="图像质量提示",
                    lines=7,
                    interactive=False,
                    elem_classes=["panel-card"],
                )

            with gr.Group(elem_classes=["section-card", "result-table-card"]):
                with gr.Accordion(
                    "查看检测明细",
                    open=False,
                    elem_classes=["result-details-accordion"],
                ):
                    visible_class_filter = gr.CheckboxGroup(
                        label="显示类别",
                        choices=[],
                        value=[],
                        interactive=False,
                        elem_classes=["compact-control"],
                    )
                    det_table = gr.Dataframe(
                        value=data.initial_detection_table,
                        headers=list(DETECTION_TABLE_COLUMNS),
                        label="检测框",
                        wrap=False,
                        interactive=False,
                    )
            summary = gr.JSON(label="参数摘要", visible=False)

    return WorkbenchComponents(
        workbench_model_status=workbench_model_status,
        patient_select=patient_select,
        clear_session_btn=clear_session_btn,
        image=image,
        run_btn=run_btn,
        example_select=example_select,
        load_example_btn=load_example_btn,
        example_info=example_info,
        batch_files=batch_files,
        batch_btn=batch_btn,
        batch_select=batch_select,
        export_batch_btn=export_batch_btn,
        export_batch_word_btn=export_batch_word_btn,
        batch_export_file=batch_export_file,
        batch_word_file=batch_word_file,
        batch_export_path=batch_export_path,
        batch_word_path=batch_word_path,
        batch_overview=batch_overview,
        model_mode=model_mode,
        model_mode_feedback=model_mode_feedback,
        device_choice=device_choice,
        conf=conf,
        iou=iou,
        use_clahe=use_clahe,
        original_output=original_output,
        model_input_output=model_input_output,
        result_output=result_output,
        comparison_section=comparison_section,
        comparison_view=comparison_view,
        result_image_path=result_image_path,
        download_result_btn=download_result_btn,
        result_image_file=result_image_file,
        visible_class_filter=visible_class_filter,
        det_table=det_table,
        advice_box=advice_box,
        quality_box=quality_box,
        summary=summary,
        report_export_menu_btn=report_export_menu_btn,
        report_export_status=report_export_status,
        word_report_path=word_report_path,
        export_word_btn=export_word_btn,
        open_word_report_dir_btn=open_word_report_dir_btn,
        word_report_file=word_report_file,
        report_path=report_path,
        export_report_btn=export_report_btn,
        open_report_dir_btn=open_report_dir_btn,
        report_file=report_file,
    )
