from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .model_files import is_advanced_model_path, is_recommended_model_path, model_label_from_path


def format_model_path_for_display(path: str | Path, *, max_chars: int = 88) -> str:
    text = str(path)
    if len(text) <= max_chars:
        return text
    keep = max(12, (max_chars - 3) // 2)
    return f"{text[:keep]}...{text[-keep:]}"


def build_model_path_compact_html(path: str | Path) -> str:
    full_path = escape(str(path))
    display_path = escape(format_model_path_for_display(path))
    return f'<div class="model-path-compact" title="{full_path}">{display_path}</div>'


def build_advanced_model_warning_html() -> str:
    return (
        '<div class="advanced-model-warning">'
        '<strong>高级模型提示</strong>'
        '<span>高级模型可能包含实验权重、last.pt 或预训练模型，答辩演示请优先使用推荐模型。</span>'
        '</div>'
    )


def build_demo_recommendation_html() -> str:
    return (
        '<div class="demo-flow-note"><strong>推荐演示流程</strong>'
        '<ol><li>使用 baseline 模型作为稳定对照。</li>'
        '<li>使用 C2f-Faster-lite 优化模型展示改进效果。</li>'
        '<li>不建议在答辩中临时选择 last.pt、未知实验权重或预训练权重。</li></ol></div>'
    )


def build_model_cards_html(cards: list[dict[str, Any]], selected_path: str | None = None) -> str:
    chunks = ['<div class="model-card-grid">']
    for card in cards:
        selected = str(selected_path or "") == str(card.get("path") or "")
        status_class = escape(str(card.get("status_class") or ("available" if card.get("available") else "missing")))
        status_text = escape(str(card.get("status_text") or ("可用" if card.get("available") else "缺失")))
        title = escape(str(card.get("title", "")))
        name = escape(str(card.get("name", "")))
        description = escape(str(card.get("description", "")))
        classes = escape(str(card.get("classes", "")))
        architecture = escape(str(card.get("architecture", "")))
        path = str(card.get("path", ""))
        dependency_note = escape(str(card.get("dependency_note", "")))
        demo_note = escape(str(card.get("demo_note", "")))
        badges = []
        if selected:
            badges.append('<span class="model-card-badge selected-badge">当前选中</span>')
        if card.get("is_default"):
            badges.append('<span class="model-card-badge default-badge">当前默认</span>')
        if card.get("is_baseline"):
            badges.append('<span class="model-card-badge baseline-badge">baseline</span>')
        if card.get("needs_custom_ultralytics"):
            badges.append('<span class="model-card-badge dependency-badge">需自定义依赖</span>')
        chunks.append(
            f"""
<div class="model-info-card {'selected' if selected else ''}">
  <div class="model-card-top">
    <span class="model-card-title">{title}</span>
    <span class="model-card-tag {status_class}">{status_text}</span>
  </div>
  <div class="model-card-badges">{''.join(badges)}</div>
  <strong>{name}</strong>
  <p>{description}</p>
  <p class="model-demo-note"><strong>推荐用途：</strong>{demo_note}</p>
  <div class="model-card-meta">类别：{classes}</div>
  <div class="model-card-meta">结构：{architecture}</div>
  <div class="model-card-meta dependency-note">{dependency_note}</div>
  {build_model_path_compact_html(path)}
</div>
"""
        )
    chunks.append("</div>")
    return "".join(chunks)


def build_workbench_model_status_html(
    selected_path: str | Path | None,
    cards: list[dict[str, Any]],
    *,
    default_model_path: str | Path,
    recommended_paths: set[str] | list[str] | tuple[str, ...] | None = None,
) -> str:
    path = str(selected_path or default_model_path)
    card = next((item for item in cards if str(item.get("path")) == path), None)
    if card:
        if card.get("is_baseline"):
            model_type = "baseline"
            title = "当前演示模型：YOLOv8m 原始结构 baseline（稳定对照）"
        elif card.get("needs_custom_ultralytics"):
            model_type = "optimized"
            title = "当前演示模型：C2f-Faster-lite 优化模型"
        else:
            model_type = "recommended"
            title = f"当前演示模型：{card.get('name', '推荐模型')}"
        status = str(card.get("demo_note") or "推荐演示模型。")
        dependency = str(card.get("dependency_note") or "无额外自定义依赖。")
        status_class = "recommended" if card.get("available") else "warning"
    else:
        model_type = "advanced / experimental"
        title = f"当前模型：{model_label_from_path(path)}"
        recommended = is_recommended_model_path(path, recommended_paths)
        advanced = is_advanced_model_path(path, recommended_paths)
        status_class = "recommended" if recommended else "warning"
        status = "推荐演示模型。" if recommended else "当前模型属于高级/实验权重，不建议答辩临时使用。"
        dependency = "高级模型可能包含 last.pt、预训练模型或早期实验权重，请确认用途后再演示。" if advanced else "无额外自定义依赖说明。"

    return f"""
<div class="workbench-model-status {status_class}">
  <strong>{escape(title)}</strong>
  <span>类型：{escape(model_type)}</span>
  <span>状态：{escape(status)}</span>
  <span>依赖：{escape(dependency)}</span>
</div>
"""
