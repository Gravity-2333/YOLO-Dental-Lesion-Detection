from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageStat

from .visualization import as_rgb_image


@dataclass
class ImageQualityResult:
    width: int
    height: int
    brightness: float
    contrast: float
    blur_score: float
    overexposed_ratio: float
    underexposed_ratio: float
    aspect_ratio: float
    quality_level: str
    warnings: list[str]
    suggestions: list[str]


def _as_rgb_image(image: Any) -> Image.Image:
    if image is None:
        raise ValueError("image is required")
    return as_rgb_image(image)


def assess_image_quality_detail(image: Image.Image) -> ImageQualityResult:
    pil_image = _as_rgb_image(image)
    width, height = pil_image.size
    gray = pil_image.convert("L")
    gray_array = np.asarray(gray)
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    gray_float = gray_array.astype(np.float32, copy=False)
    laplacian = (
        -4.0 * gray_float[1:-1, 1:-1]
        + gray_float[:-2, 1:-1]
        + gray_float[2:, 1:-1]
        + gray_float[1:-1, :-2]
        + gray_float[1:-1, 2:]
    )
    blur_score = float(laplacian.var()) if laplacian.size else 0.0
    overexposed_ratio = float(np.mean(gray_array >= 245))
    underexposed_ratio = float(np.mean(gray_array <= 10))
    aspect_ratio = max(width, height) / max(1, min(width, height))

    warnings: list[str] = []
    suggestions: list[str] = []
    risk_points = 0

    if min(width, height) < 512:
        warnings.append("图像分辨率偏低，细小病变区域的模型识别稳定性可能下降。")
        risk_points += 1
    if brightness < 45:
        warnings.append("图像整体偏暗，建议确认牙片曝光或阅片窗宽窗位。")
        risk_points += 1
    elif brightness > 220:
        warnings.append("图像整体偏亮，建议确认牙片曝光或显示设置。")
        risk_points += 1
    if contrast < 28:
        warnings.append("图像对比度偏低，可能影响细小病变边界识别。")
        suggestions.append("建议尝试开启 CLAHE 增强后对照查看。")
        risk_points += 1
    if blur_score < 50:
        warnings.append("图像可能存在明显模糊，建议尽量使用更清晰的牙科影像。")
        risk_points += 2
    elif blur_score < 100:
        warnings.append("图像清晰度一般，建议结合原始影像谨慎复核。")
        risk_points += 1
    if overexposed_ratio > 0.12:
        warnings.append("图像存在较多过亮区域，可能影响细小病变识别。")
        risk_points += 1
    if underexposed_ratio > 0.12:
        warnings.append("图像存在较多过暗区域，建议确认曝光或阅片设置。")
        risk_points += 1
    if aspect_ratio > 4:
        warnings.append("图像宽高比非常极端，建议确认是否上传完整牙片而不是过窄裁剪。")
        risk_points += 1

    if not suggestions and (contrast < 45 or brightness < 60):
        suggestions.append("可尝试开启 CLAHE 增强后与原始结果对照。")
    if not warnings:
        suggestions.append("当前未发现明显输入质量风险。")

    if risk_points >= 3:
        quality_level = "较差"
    elif risk_points >= 1:
        quality_level = "一般"
    else:
        quality_level = "良好"

    return ImageQualityResult(
        width=width,
        height=height,
        brightness=brightness,
        contrast=contrast,
        blur_score=blur_score,
        overexposed_ratio=overexposed_ratio,
        underexposed_ratio=underexposed_ratio,
        aspect_ratio=aspect_ratio,
        quality_level=quality_level,
        warnings=warnings,
        suggestions=suggestions,
    )


def format_quality_text(result: ImageQualityResult) -> str:
    warnings = result.warnings or ["当前未发现明显输入质量风险。"]
    suggestions = result.suggestions or ["建议结合原始影像和专业牙科医生检查进行复核。"]
    return "\n".join(
        [
            "图像质量提示",
            "",
            "基础信息：",
            f"- 尺寸：{result.width} x {result.height}",
            f"- 平均亮度：{result.brightness:.1f}",
            f"- 对比度估计：{result.contrast:.1f}",
            f"- 模糊评分：{result.blur_score:.1f}",
            f"- 过曝比例：{result.overexposed_ratio:.1%}",
            f"- 欠曝比例：{result.underexposed_ratio:.1%}",
            "",
            "综合判断：",
            f"- 图像质量等级：{result.quality_level}",
            "",
            "风险提示：",
            *[f"- {item}" for item in warnings],
            "",
            "建议：",
            *[f"- {item}" for item in suggestions],
        ]
    )
