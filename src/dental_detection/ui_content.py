from __future__ import annotations

from html import escape
from itertools import count

from .ai_defaults import SAFETY_NOTICE


_TOAST_SEQUENCE = count(1)


def _feedback_content(message: str) -> str:
    return escape(str(message)).replace("\n", "<br>")


def toast_html(message: str, kind: str = "success") -> str:
    if not message:
        return ""
    sequence = next(_TOAST_SEQUENCE)
    return (
        f'<div class="app-toast app-toast-{kind}" data-toast-sequence="{sequence}">'
        f"{_feedback_content(message)}</div>"
    )


def inline_status_html(message: str, kind: str = "success") -> str:
    if not message:
        return ""
    return (
        f'<div class="app-inline-status app-inline-status-{kind}" role="status">'
        f"{_feedback_content(message)}</div>"
    )


def section_heading(title: str, description: str) -> str:
    return (
        '<div class="section-heading">'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(description)}</p>"
        "</div>"
    )


APP_HEADER_HTML = """
<header class="app-header">
  <div class="app-brand-mark" aria-hidden="true">AI</div>
  <div class="app-brand-copy">
    <p class="app-eyebrow">CLINICAL DENTAL WORKSPACE</p>
    <h1 class="app-title">智能健康牙齿分析</h1>
    <p class="app-subtitle">牙科影像辅助筛查、AI 分析与病例管理</p>
  </div>
  <div class="app-header-meta"><strong>本地工作区</strong><span>医生主导，模型辅助</span></div>
</header>
"""

WORKBENCH_HELP_TEXT = (
    "支持 PNG、JPG、JPEG、BMP、WEBP、TIF、TIFF 格式图片。\n\n"
    "置信度表示模型对检测框的把握程度，不等同于疾病严重程度。\n\n"
    "CLAHE 适合低对比度牙片；如果图像本身清晰，可保持关闭。\n\n"
    "报告默认导出完整检测结果；界面中的类别显示开关只影响当前查看和结果图下载。\n\n"
    f"{SAFETY_NOTICE}"
)

AI_CHAT_INTRO_HTML = """
<div class="card-heading">
  <div><h2>AI 问答</h2><p>基于当前检测文字摘要继续追问，不上传牙科影像；回复仅供辅助参考，不替代专业牙科医生诊断。</p></div>
</div>
"""

RECORD_BOUNDARY_HTML = """
<div class="record-boundary-strip">
  <div><strong>保存位置</strong><span>本机数据目录，可在设置中查看</span></div>
  <div><strong>原始牙片</strong><span>默认不随病例和历史保存</span></div>
  <div><strong>云端传输</strong><span>记录不会自动上传云端</span></div>
</div>
"""


CASE_INTRO_HTML = """
<div class="card-heading"><div><h2>病例记录</h2><p>保存检测摘要、检测框和建议，便于后续复查。</p></div></div>
""" + RECORD_BOUNDARY_HTML

HISTORY_INTRO_HTML = """
<div class="card-heading"><div><h2>检测历史</h2><p>查看已保存的检测摘要，便于回顾分析结果。</p></div></div>
""" + RECORD_BOUNDARY_HTML
