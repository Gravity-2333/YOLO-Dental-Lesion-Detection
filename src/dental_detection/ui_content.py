from __future__ import annotations

from html import escape
from itertools import count

from .ai_defaults import SAFETY_NOTICE


_TOAST_SEQUENCE = count(1)
_HELP_SEQUENCE = count(1)


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


def context_help_html(
    title: str,
    message: str,
    *,
    kind: str = "info",
) -> str:
    tooltip_id = f"context-help-{next(_HELP_SEQUENCE)}"
    safe_kind = "warning" if kind == "warning" else "info"
    symbol = "!" if safe_kind == "warning" else "?"
    paragraphs = "".join(
        f"<p>{escape(part.strip()).replace(chr(10), '<br>')}</p>"
        for part in str(message).split("\n\n")
        if part.strip()
    )
    return (
        f'<div class="context-help context-help-{safe_kind}">'
        f'<span class="context-help-trigger" tabindex="0" '
        f'aria-label="{escape(title)}" aria-describedby="{tooltip_id}">'
        f'<span aria-hidden="true">{symbol}</span></span>'
        f'<div class="context-help-bubble" id="{tooltip_id}" role="tooltip">'
        '<div class="context-help-bubble-card">'
        f'<strong>{escape(title)}</strong>{paragraphs}'
        "</div></div></div>"
    )


def field_label_with_help_html(
    label: str,
    help_title: str,
    help_text: str,
) -> str:
    return (
        '<div class="settings-field-label">'
        f'<span class="settings-field-label-text">{escape(label)}</span>'
        f'{context_help_html(help_title, help_text)}'
        "</div>"
    )


def section_heading(
    title: str,
    description: str,
    *,
    help_title: str | None = None,
    help_text: str | None = None,
    help_kind: str = "info",
) -> str:
    help_html = (
        context_help_html(help_title or "说明", help_text, kind=help_kind)
        if help_text
        else ""
    )
    return (
        '<div class="section-heading">'
        '<div class="section-heading-copy">'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(description)}</p>"
        "</div>"
        f"{help_html}"
        "</div>"
    )


APP_HEADER_HTML = """
<div class="app-header-shell">
  <header class="app-header" data-app-header>
    <div class="app-header-inner">
      <div class="app-header-brand">
        <div class="app-brand-mark" aria-hidden="true">AI</div>
        <div class="app-brand-copy">
          <p class="app-eyebrow">CLINICAL DENTAL WORKSPACE</p>
          <h1 class="app-title">智能健康牙齿分析</h1>
          <p class="app-subtitle">牙科影像辅助筛查、AI 分析与病例管理</p>
        </div>
      </div>
      <nav class="app-primary-nav" aria-label="主导航">
        <ul class="app-primary-nav-list">
          <li><button type="button" class="app-nav-link" data-app-target="首页">首页</button></li>
          <li><button type="button" class="app-nav-link" data-app-target="检测工作台">检测工作台</button></li>
          <li><button type="button" class="app-nav-link" data-app-target="AI 问答">AI 问答</button></li>
          <li><button type="button" class="app-nav-link" data-app-target="病例记录">病例记录</button></li>
          <li><button type="button" class="app-nav-link" data-app-target="检测历史">检测历史</button></li>
          <li><button type="button" class="app-nav-link" data-app-target="设置">设置</button></li>
        </ul>
      </nav>
    </div>
  </header>
</div>
"""

WORKBENCH_HELP_TEXT = (
    "支持 PNG、JPG、JPEG、BMP、WEBP、TIF、TIFF 格式图片。\n\n"
    "置信度表示模型对检测框的把握程度，不等同于疾病严重程度。\n\n"
    "CLAHE 适合低对比度牙片；如果图像本身清晰，可保持关闭。\n\n"
    "报告默认导出完整检测结果；界面中的类别显示开关只影响当前查看和结果图下载。\n\n"
    f"{SAFETY_NOTICE}"
)

DISPLAY_OPTIONS_HELP = (
    "对比模型会在单张分析时运行两组模型。\n\n"
    "参数摘要用于查看推理配置和检测数量。"
)

MODEL_SELECTION_HELP = (
    "刷新会扫描模型目录及子目录中的受支持模型文件；三点按钮用于弹出路径选择器并切换模型目录。\n\n"
    "优化模型适合常规检测；兼容模型不依赖自定义结构，可在优化模型无法加载时使用。\n\n"
    "高级路径设置主要用于维护和实验权重，普通使用无需展开。"
)

AI_INTERFACE_HELP = (
    "兼容 OpenAI Chat Completions。\n\n"
    "测试请求只发送“请只回复 OK”，字段限定为 model、messages、temperature、max_tokens。"
)

STORAGE_HELP = (
    "对话、导出和病例记录会保存在该数据根目录下。更换目录会切换后续保存位置，不会自动搬移旧目录数据。\n\n"
    "三点按钮会弹出路径选择器；自动保存的对话和检测历史会按设定数量保留。\n\n"
    "检测历史默认只保存摘要和检测框，不保存原始上传图。"
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
