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
    <div class="eyebrow">医院与个人辅助筛查工作台</div>
    <h1 class="app-title">牙齿病变区域识别</h1>
    <p class="app-subtitle">上传牙科影像，查看模型输入、检测框和辅助建议。结果仅供参考，不能替代专业牙科医生诊断。</p>
  </div>
  <span class="status-badge">Dental AI Workbench</span>
</header>
"""

WORKBENCH_GUIDE_HTML = """
<div class="guide-steps">
  <span>1. 上传影像</span>
  <span>2. 选择模型</span>
  <span>3. 开始分析</span>
  <span>4. 查看并导出</span>
</div>
<div class="workflow-hint">
  <strong>演示提示</strong>
  <span>baseline 适合稳定对照；C2f-Faster-lite 为优化模型，依赖同级 ../yolov8-train。模型切换在“设置 - 模型选择”中完成。</span>
</div>
"""

WORKBENCH_HELP_TEXT = (
    "支持 PNG、JPG、JPEG、BMP、WEBP、TIF、TIFF 格式图片。\n\n"
    "置信度表示模型对检测框的把握程度，不等同于疾病严重程度。\n\n"
    "CLAHE 适合低对比度牙片；如果图像本身清晰，可保持关闭。\n\n"
    "报告默认导出完整检测结果；界面中的类别显示开关只影响当前查看和结果图下载。\n\n"
    f"{SAFETY_NOTICE}"
)

RESULT_STAGE_HTML = """
<div class="result-stage-note">
  <strong>结果区</strong>
  <span>未检测时这里会保持空状态；开始分析后将显示原图、模型输入、检测框、辅助建议和导出入口。</span>
</div>
"""

AI_CHAT_INTRO_HTML = """
<div class="card-heading">
  <div><h2>AI 问答</h2><p>完成检测后，可以继续追问关注区域和复查建议。</p></div>
  <span class="status-badge">自动保存可在设置中调整</span>
</div>
<div class="notice-grid">
  <div class="notice-item privacy-note"><strong>隐私边界</strong><span>默认只发送检测文本摘要，不上传牙片图片。</span></div>
  <div class="notice-item clinical-note"><strong>安全边界</strong><span>AI 回复仅供辅助参考，不能替代专业牙科医生诊断。</span></div>
  <div class="notice-item settings-note"><strong>接口配置</strong><span>如需联网问答，请先在“设置 - AI 建议”中填写 Base URL、模型和 API Key。</span></div>
</div>
"""

CASE_INTRO_HTML = """
<div class="card-heading"><div><h2>病例记录</h2><p>保存检测摘要、检测框和建议，便于后续复查。</p></div></div>
<div class="notice-grid">
  <div class="notice-item privacy-note"><strong>本地保存</strong><span>病例记录保存在本机数据目录，默认不上传云端。</span></div>
  <div class="notice-item clinical-note"><strong>不保存原片</strong><span>记录仅保存摘要、检测框和建议，不自动保存原始牙片图片。</span></div>
</div>
"""
