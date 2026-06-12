from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .config import DEFAULT_MODEL_NAME
from .result_levels import CLASS_DISPLAY_NAMES


CLASS_LEGEND = [
    {
        "class": "Caries",
        "中文名称": "龋齿",
        "color": "#eb583c",
        "说明": "模型检测到疑似龋坏相关区域，建议结合症状和牙科检查复核。",
    },
    {
        "class": "Periapical Lesion",
        "中文名称": "根尖周病变",
        "color": "#2092e6",
        "说明": "模型检测到疑似根尖周相关异常区域，建议由牙科医生结合影像复查。",
    },
    {
        "class": "Impacted",
        "中文名称": "阻生牙",
        "color": "#28aa6e",
        "说明": "模型检测到疑似阻生牙相关区域，建议咨询牙科医生评估。",
    },
]


def _path_exists(value: Any) -> bool:
    try:
        return Path(value).expanduser().exists()
    except (TypeError, OSError, RuntimeError):
        return False


def build_model_cards(model_registry: dict[str, dict[str, Any]], default_model_name: str = DEFAULT_MODEL_NAME) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for name, info in model_registry.items():
        path = Path(info.get("path", ""))
        architecture = str(info.get("architecture", "YOLOv8"))
        role = str(info.get("role", "候选模型"))
        is_default = name == default_model_name
        if is_default:
            title = "推荐模型"
            description = "综合速度、资源占用和识别表现，适合日常辅助筛查。"
        elif "lite" in architecture.casefold() or "优化" in role:
            title = "轻量优化模型"
            description = "结构更轻，推理资源消耗更低，适合优先考虑运行效率的场景。"
        else:
            title = "原始模型"
            description = "YOLOv8m 原始结构候选模型，适合与优化模型进行效果对照。"
        cards.append(
            {
                "title": title,
                "name": name,
                "description": description,
                "architecture": architecture,
                "role": role,
                "path": str(path),
                "available": _path_exists(path),
                "tag": "推荐" if is_default else role,
                "classes": "、".join(CLASS_DISPLAY_NAMES.values()),
                "metrics": info.get("metrics", {}),
            }
        )
    return cards


def get_model_info_cards(model_registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return build_model_cards(model_registry)


def format_model_info_markdown(model_info: dict[str, Any]) -> str:
    metrics = model_info.get("metrics") or {}
    metric_lines = []
    for key, label in [
        ("test_mAP50", "mAP50"),
        ("test_mAP50_95", "mAP50-95"),
        ("params", "参数量"),
        ("gflops", "GFLOPs"),
    ]:
        if key in metrics:
            metric_lines.append(f"- {label}：{escape(str(metrics[key]))}")
    metric_text = "\n".join(metric_lines) if metric_lines else "- 暂无指标摘要"
    name = escape(str(model_info.get("name", "未知模型")))
    architecture = escape(str(model_info.get("architecture", "YOLOv8 目标检测模型")))
    role = escape(str(model_info.get("role", "牙齿病变区域辅助识别")))
    return f"""## 当前模型：{name}

- 模型类型：{architecture}
- 模型定位：{role}
- 可识别类别：{"、".join(CLASS_DISPLAY_NAMES.values())}
- 模型状态：{"可用" if model_info.get("available") else "模型文件未找到"}

### 输入图片要求
- 建议使用清晰、完整、曝光正常的牙科影像。
- 低分辨率、严重模糊、过曝、欠曝或遮挡明显的图片可能影响识别结果。

### 推荐使用场景
- 牙齿病变区域辅助筛查。
- 批量影像初筛和复查前资料整理。
- 结合牙科医生判断进行疑似区域定位沟通。

### 不适用场景
- 本系统不适用于最终诊断。
- 本系统不提供治疗方案。
- 本系统不提供药物建议。
- 未检测到目标不代表不存在病变。

### 结果解释
模型输出为疑似区域检测框和置信度。置信度表示模型对检测框的把握程度，不等同于疾病严重程度，也不能替代专业牙科医生诊断。

### 指标摘要
{metric_text}

### 安全声明
本结果仅供辅助参考，不能替代专业牙科医生诊断。
"""


def model_cards_html(cards: list[dict[str, Any]], selected_path: str | None = None) -> str:
    chunks = ['<div class="model-card-grid">']
    for card in cards:
        selected = str(selected_path or "") == str(card.get("path") or "")
        status_class = "available" if card.get("available") else "missing"
        title = escape(str(card.get("title", "")))
        name = escape(str(card.get("name", "")))
        description = escape(str(card.get("description", "")))
        classes = escape(str(card.get("classes", "")))
        architecture = escape(str(card.get("architecture", "")))
        chunks.append(
            f"""
<div class="model-info-card {'selected' if selected else ''}">
  <div class="model-card-top">
    <span class="model-card-title">{title}</span>
    <span class="model-card-tag {status_class}">{'可用' if card.get('available') else '缺失'}</span>
  </div>
  <strong>{name}</strong>
  <p>{description}</p>
  <div class="model-card-meta">类别：{classes}</div>
  <div class="model-card-meta">结构：{architecture}</div>
</div>
"""
        )
    chunks.append("</div>")
    return "".join(chunks)


def legend_html() -> str:
    items = []
    for item in CLASS_LEGEND:
        items.append(
            f"""
<div class="legend-item">
  <span class="legend-swatch" style="background:{item['color']}"></span>
  <strong>{item['中文名称']}</strong>
  <span>{item['说明']}</span>
</div>
"""
        )
    return '<div class="result-legend">' + "".join(items) + "</div>"


def legend_markdown() -> str:
    lines = ["图例与类别说明："]
    for item in CLASS_LEGEND:
        lines.append(f"- {item['中文名称']}：{item['说明']}")
    return "\n".join(lines)
