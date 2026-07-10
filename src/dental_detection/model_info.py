from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .config import DEFAULT_MODEL_NAME
from .model_files import is_supported_model_artifact
from .model_ui import build_model_cards_html
from .result_levels import CLASS_DISPLAY_NAMES
from .runtime_paths import CUSTOM_ULTRALYTICS_PATH


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
        return is_supported_model_artifact(Path(value).expanduser())
    except (TypeError, OSError, RuntimeError):
        return False


def build_model_cards(model_registry: dict[str, dict[str, Any]], default_model_name: str = DEFAULT_MODEL_NAME) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    custom_ultralytics_available = (CUSTOM_ULTRALYTICS_PATH / "ultralytics").is_dir()
    for name, info in model_registry.items():
        path = Path(info.get("path", ""))
        architecture = str(info.get("architecture", "YOLOv8"))
        role = str(info.get("role", "候选模型"))
        is_default = name == default_model_name
        is_baseline = "原始" in name or architecture == "YOLOv8m"
        needs_custom_ultralytics = "C2f-Faster-lite" in name or "C2f-Faster-lite" in architecture
        artifact_available = _path_exists(path)
        dependency_available = (not needs_custom_ultralytics) or custom_ultralytics_available
        available = artifact_available and dependency_available
        if is_default:
            title = "优化模型"
            description = "综合速度、资源占用和识别表现，适合日常辅助筛查。"
        elif "lite" in architecture.casefold() or "优化" in role:
            title = "轻量优化模型"
            description = "结构更轻，推理资源消耗更低，适合优先考虑运行效率的场景。"
        else:
            title = "兼容模型"
            description = "YOLOv8m 原始结构，兼容性高，适合对运行环境兼容性要求较高的场景。"
        if needs_custom_ultralytics:
            dependency_note = "依赖同级目录 ../yolov8-train 中的自定义 ultralytics 代码。"
            usage_note = (
                "适合常规辅助筛查和批量检测。"
                if custom_ultralytics_available
                else "运行依赖缺失，请改用兼容模型。"
            )
        else:
            dependency_note = "不依赖自定义 ultralytics。"
            usage_note = "适合环境兼容、基础检测或模型效果对比。"
        if not artifact_available:
            status_text = "缺失"
            status_class = "missing"
        elif not dependency_available:
            status_text = "依赖缺失"
            status_class = "dependency-missing"
        else:
            status_text = "可用"
            status_class = "available"
        cards.append(
            {
                "title": title,
                "name": name,
                "description": description,
                "architecture": architecture,
                "role": role,
                "path": str(path),
                "available": available,
                "artifact_available": artifact_available,
                "dependency_available": dependency_available,
                "dependency_note": dependency_note,
                "usage_note": usage_note,
                "is_default": is_default,
                "is_baseline": is_baseline,
                "needs_custom_ultralytics": needs_custom_ultralytics,
                "status_text": status_text,
                "status_class": status_class,
                "tag": "默认" if is_default else ("baseline" if is_baseline else role),
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
    status_text = escape(str(model_info.get("status_text") or ("可用" if model_info.get("available") else "不可用或格式不支持")))
    dependency_note = escape(str(model_info.get("dependency_note") or "无额外自定义依赖说明。"))
    usage_note = escape(str(model_info.get("usage_note") or "使用前请确认模型文件可正常加载。"))
    path = escape(str(model_info.get("path", "")))
    return f"""## 当前模型：{name}

- 模型类型：{architecture}
- 模型定位：{role}
- 可识别类别：{"、".join(CLASS_DISPLAY_NAMES.values())}
- 模型状态：{status_text}
- 模型路径：`{path}`

### 使用与依赖
- {usage_note}
- {dependency_note}

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
    return build_model_cards_html(cards, selected_path)


def legend_html() -> str:
    items = []
    for item in CLASS_LEGEND:
        items.append(
            f"""
<div class="legend-item">
  <span class="legend-swatch" style="background:{item['color']}"></span>
  <strong>{item['中文名称']}</strong>
</div>
"""
        )
    return '<div class="result-legend">' + "".join(items) + "</div>"


def legend_markdown() -> str:
    lines = ["图例与类别说明："]
    for item in CLASS_LEGEND:
        lines.append(f"- {item['中文名称']}：{item['说明']}")
    return "\n".join(lines)
