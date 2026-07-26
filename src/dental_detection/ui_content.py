from __future__ import annotations

from html import escape

from .ai_defaults import SAFETY_NOTICE


def section_heading(title: str, description: str) -> str:
    return (
        '<div class="section-heading">'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(description)}</p>"
        "</div>"
    )


APP_HEADER_HTML = """
<header class="app-header">
  <div>
    <h1 class="app-title">牙齿病变区域识别</h1>
    <p class="app-subtitle">牙科影像辅助筛查、记录与报告管理</p>
  </div>
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
  <div><h2>AI 问答</h2><p>完成检测后，可以继续追问关注区域和复查建议。</p></div>
</div>
<p class="ai-privacy-note">仅发送检测文字摘要，不上传牙科影像；回复仅供辅助参考，不替代专业牙科医生诊断。</p>
"""

CASE_INTRO_HTML = """
<div class="card-heading"><div><h2>病例记录</h2><p>保存检测摘要、检测框和建议，便于后续复查。</p></div></div>
"""
