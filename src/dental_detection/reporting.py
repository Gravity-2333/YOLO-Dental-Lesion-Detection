from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image

from .result_levels import enrich_detection_row


@dataclass
class SingleReportData:
    image_name: str
    created_at: str
    model_name: str
    original_image: Image.Image
    model_input_image: Image.Image | None
    annotated_image: Image.Image
    detections: list[dict[str, Any]]
    advice: str
    quality_text: str
    summary: dict[str, Any]
    safety_notice: str


def _add_paragraphs(document, text: str) -> None:
    for line in str(text or "").splitlines() or [""]:
        document.add_paragraph(line)


def _save_temp_image(image: Image.Image, root: Path, name: str) -> Path:
    path = root / name
    image.convert("RGB").save(path)
    return path


def _summary_value(summary: dict[str, Any], *names: str, default: str = "-") -> Any:
    for name in names:
        if name in summary:
            return summary[name]
    return default


def _yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def export_single_docx_report(data: SingleReportData, output_dir: Path) -> Path:
    from docx import Document
    from docx.shared import Inches

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "牙齿病变区域辅助识别报告.docx"
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"牙齿病变区域辅助识别报告_{counter:02d}.docx"
        counter += 1

    document = Document()
    document.add_heading("牙齿病变区域辅助识别报告", level=0)
    notice = document.add_paragraph()
    run = notice.add_run(data.safety_notice)
    run.bold = True

    document.add_paragraph(f"生成时间：{data.created_at}")
    document.add_paragraph(f"图片名称：{data.image_name}")
    document.add_paragraph(f"使用模型：{data.model_name}")
    document.add_paragraph("报告类型：单张影像检测报告")

    document.add_heading("一、影像与检测结果", level=1)
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for caption, image, file_name in [
            ("图 1 原始上传图", data.original_image, "original.png"),
            ("图 2 检测结果图", data.annotated_image, "annotated.png"),
            ("图 3 实际送入模型的图像", data.model_input_image, "model_input.png"),
        ]:
            if image is None:
                continue
            document.add_paragraph(caption)
            image_path = _save_temp_image(image, temp_root, file_name)
            document.add_picture(str(image_path), width=Inches(5.8))

    document.add_heading("二、检测摘要", level=1)
    enriched = [enrich_detection_row(det) for det in data.detections]
    if enriched:
        document.add_paragraph(f"本次共检测到 {len(enriched)} 个疑似目标区域。")
        counts: dict[str, int] = {}
        for row in enriched:
            display_name = row["中文名称"]
            counts[display_name] = counts.get(display_name, 0) + 1
        for name, count in sorted(counts.items()):
            document.add_paragraph(f"- {name}：{count} 处")
    else:
        document.add_paragraph(
            "本次未检测到明确目标框。该结果不代表不存在病变，仍需结合原始影像质量、临床症状和专业牙科检查进行判断。"
        )

    document.add_heading("三、检测框明细", level=1)
    headers = ["序号", "类别", "中文名称", "置信度", "关注等级", "x1", "y1", "x2", "y2"]
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
    for index, row in enumerate(enriched, start=1):
        cells = table.add_row().cells
        values = [
            index,
            row["class"],
            row["中文名称"],
            row["confidence"],
            row["关注等级"],
            row["x1"],
            row["y1"],
            row["x2"],
            row["y2"],
        ]
        for cell, value in zip(cells, values):
            cell.text = str(value)

    document.add_heading("四、图像质量提示", level=1)
    _add_paragraphs(document, data.quality_text)

    document.add_heading("五、辅助建议", level=1)
    _add_paragraphs(document, data.advice)

    document.add_heading("六、技术参数摘要", level=1)
    document.add_paragraph(f"推理尺寸：{_summary_value(data.summary, '推理尺寸')}")
    document.add_paragraph(f"置信度阈值：{_summary_value(data.summary, '置信度阈值', 'conf')}")
    document.add_paragraph(f"IoU 阈值：{_summary_value(data.summary, 'IoU阈值', 'iou')}")
    document.add_paragraph(f"CLAHE 增强：{_yes_no(_summary_value(data.summary, 'CLAHE增强'))}")
    document.add_paragraph(f"运行设备：{_summary_value(data.summary, '运行设备')}")
    document.add_paragraph(f"模型名称：{data.model_name}")

    document.save(output_path)
    return output_path
