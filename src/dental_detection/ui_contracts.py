from __future__ import annotations

from collections.abc import Mapping
from typing import Any


# This order mirrors the Gradio component list wired in app.build_app().
# Callback code should build values by name and let this module enforce order.
COMMON_OUTPUT_KEYS = (
    "original",
    "model_input",
    "result",
    "highres_result",
    "crop_gallery",
    "crop_status",
    "result_image_file",
    "result_image_path",
    "download_result_button",
    "visible_class_filter",
    "detection_table",
    "advice",
    "quality",
    "summary",
    "batch_overview",
    "batch_state",
    "batch_select",
    "chatbot",
    "chat_state",
    "batch_export_file",
    "batch_export_path",
    "batch_export_button",
    "batch_word_file",
    "batch_word_path",
    "batch_word_button",
    "chat_export_file",
    "chat_export_path",
    "word_report_file",
    "word_report_path",
    "word_export_button",
    "zip_report_file",
    "zip_report_path",
    "zip_export_button",
    "save_case_button",
)

COMMON_OUTPUT_QUALITY_INDEX = COMMON_OUTPUT_KEYS.index("quality")


def common_output_values(values: Mapping[str, Any]) -> tuple[Any, ...]:
    expected = set(COMMON_OUTPUT_KEYS)
    actual = set(values)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        details = []
        if missing:
            details.append(f"缺少：{', '.join(sorted(missing))}")
        if extra:
            details.append(f"未知：{', '.join(sorted(extra))}")
        raise ValueError(f"主流程 UI 输出契约不匹配（{'；'.join(details)}）")
    return tuple(values[key] for key in COMMON_OUTPUT_KEYS)


def common_output_components(components: Mapping[str, Any]) -> list[Any]:
    return list(common_output_values(components))
