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
          <li class="app-nav-menu-item app-nav-menu-item-has-children">
            <button type="button" class="app-nav-link app-nav-test-trigger" aria-haspopup="true" aria-expanded="false">
              <span>Test</span><span class="app-nav-chevron" aria-hidden="true"></span>
            </button>
            <ul class="app-nav-submenu app-nav-submenu-level-1" aria-label="Test 测试菜单">
              <li><button type="button" data-app-target="检测工作台" data-workbench-target="单张分析">单张分析</button></li>
              <li><button type="button" data-app-target="检测工作台" data-workbench-target="批量分析">批量分析</button></li>
              <li class="app-nav-menu-item app-nav-menu-item-has-children">
                <button type="button" class="app-nav-submenu-trigger" aria-haspopup="true" aria-expanded="false">
                  <span>系统页面</span><span class="app-nav-chevron app-nav-chevron-side" aria-hidden="true"></span>
                </button>
                <ul class="app-nav-submenu app-nav-submenu-level-2" aria-label="系统页面二级菜单">
                  <li><button type="button" data-app-target="设置">设置</button></li>
                  <li><button type="button" data-app-target="检测历史">检测历史</button></li>
                </ul>
              </li>
            </ul>
          </li>
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
