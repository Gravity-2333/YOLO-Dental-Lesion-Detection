from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.config import DEFAULT_MODEL_PATH, MODEL_REGISTRY, PROJECT_ROOT as APP_PROJECT_ROOT
from src.dental_detection.model_info import build_model_cards
from src.dental_detection.model_ui import (
    build_advanced_model_warning_html,
    build_demo_recommendation_html,
    build_model_path_compact_html,
    build_workbench_model_status_html,
    format_model_path_for_display,
)


def run_checks() -> None:
    cards = build_model_cards(MODEL_REGISTRY)
    recommended_paths = {str(info["path"]) for info in MODEL_REGISTRY.values()}
    baseline_path = str(MODEL_REGISTRY["YOLOv8m 原始结构"]["path"])
    optimized_path = str(MODEL_REGISTRY["YOLOv8m C2f-Faster-lite"]["path"])

    baseline_html = build_workbench_model_status_html(
        baseline_path,
        cards,
        default_model_path=str(DEFAULT_MODEL_PATH),
        recommended_paths=recommended_paths,
    )
    if "兼容模型" not in baseline_html:
        raise AssertionError("原始结构状态 HTML 缺少兼容模型标识")

    optimized_html = build_workbench_model_status_html(
        optimized_path,
        cards,
        default_model_path=str(DEFAULT_MODEL_PATH),
        recommended_paths=recommended_paths,
    )
    if "优化模型" not in optimized_html:
        raise AssertionError("C2f-Faster-lite 状态 HTML 缺少优化模型标识")

    advanced_path = str(APP_PROJECT_ROOT / "models" / "pretrained" / "yolov8n.pt")
    advanced_html = build_workbench_model_status_html(
        advanced_path,
        cards,
        default_model_path=str(DEFAULT_MODEL_PATH),
        recommended_paths=recommended_paths,
    )
    if "请确认来源和兼容性" not in advanced_html:
        raise AssertionError("高级模型状态 HTML 缺少兼容性提示")

    long_path = "E:/" + "/".join(["very_long_model_directory"] * 8) + "/weights/best.pt"
    compact_text = format_model_path_for_display(long_path, max_chars=60)
    compact_html = build_model_path_compact_html(long_path)
    if "..." not in compact_text or compact_text == long_path:
        raise AssertionError("长路径展示文本未正确省略")
    if f'title="{long_path}"' not in compact_html:
        raise AssertionError("长路径 HTML 未保留完整 title")

    if not build_demo_recommendation_html().strip():
        raise AssertionError("模型选择建议为空")
    if not build_advanced_model_warning_html().strip():
        raise AssertionError("高级模型警告为空")


def main() -> None:
    run_checks()
    print("PASS check_model_ui_helpers")


if __name__ == "__main__":
    main()
