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
        '<span>高级列表可能包含实验权重、last.pt 或预训练模型，请确认来源和兼容性后再使用。</span>'
        '</div>'
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
        usage_note = escape(str(card.get("usage_note") or card.get("demo_note", "")))
        badges = []
        if selected:
            badges.append('<span class="model-card-badge selected-badge">当前选中</span>')
        if card.get("is_default"):
            badges.append('<span class="model-card-badge default-badge">当前默认</span>')
        if card.get("is_baseline"):
            badges.append('<span class="model-card-badge baseline-badge">兼容性高</span>')
        if card.get("needs_custom_ultralytics"):
            badges.append('<span class="model-card-badge dependency-badge">优化结构</span>')
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
  <p class="model-demo-note"><strong>适用场景：</strong>{usage_note}</p>
  <div class="model-card-meta">类别：{classes}</div>
  <div class="model-card-meta">结构：{architecture}</div>
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
            model_type = "兼容模型"
            title = "当前模型：YOLOv8m 原始结构"
        elif card.get("needs_custom_ultralytics"):
            model_type = "优化模型"
            title = "当前模型：C2f-Faster-lite"
        else:
            model_type = "检测模型"
            title = f"当前模型：{card.get('name', '推荐模型')}"
        status = str(card.get("status_text") or ("可用" if card.get("available") else "不可用"))
        status_class = "recommended" if card.get("available") else "warning"
    else:
        model_type = "自定义模型"
        title = f"当前模型：{model_label_from_path(path)}"
        recommended = is_recommended_model_path(path, recommended_paths)
        advanced = is_advanced_model_path(path, recommended_paths)
        status_class = "recommended" if recommended else "warning"
        status = "可用" if recommended else (
            "请确认来源和兼容性" if advanced else "请确认模型可正常加载"
        )

    return f"""
<div class="workbench-model-status {status_class}">
  <strong>{escape(title)}</strong>
  <span>类型：{escape(model_type)}</span>
  <span>状态：{escape(status)}</span>
</div>
"""
