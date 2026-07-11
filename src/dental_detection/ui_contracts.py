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

COMMON_INPUT_KEYS = (
    "model_mode",
    "patient_id",
    "primary_model_path",
    "compare_model_path",
    "conf",
    "iou",
    "device_choice",
    "use_clahe",
    "enable_compare",
    "show_summary",
    "ai_enabled",
    "base_url",
    "ai_model",
    "key_mode",
    "env_api_key",
    "direct_api_key_hidden",
    "direct_api_key_visible",
    "direct_key_visible",
    "save_key",
    "auto_save",
    "storage_dir",
    "custom_prompt",
    "advice_style",
    "save_history",
    "history_limit",
)

COMMON_OUTPUT_QUALITY_INDEX = COMMON_OUTPUT_KEYS.index("quality")


def _ordered_values(keys: tuple[str, ...], values: Mapping[str, Any], label: str) -> tuple[Any, ...]:
    expected = set(keys)
    actual = set(values)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        details = []
        if missing:
            details.append(f"缺少：{', '.join(sorted(missing))}")
        if extra:
            details.append(f"未知：{', '.join(sorted(extra))}")
        raise ValueError(f"{label}契约不匹配（{'；'.join(details)}）")
    return tuple(values[key] for key in keys)


def common_output_values(values: Mapping[str, Any]) -> tuple[Any, ...]:
    return _ordered_values(COMMON_OUTPUT_KEYS, values, "主流程 UI 输出")


def common_output_components(components: Mapping[str, Any]) -> list[Any]:
    return list(common_output_values(components))


def common_input_components(components: Mapping[str, Any]) -> list[Any]:
    return list(_ordered_values(COMMON_INPUT_KEYS, components, "主流程 UI 输入"))
