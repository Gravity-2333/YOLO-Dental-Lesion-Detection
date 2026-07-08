from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .assistant import ensure_app_dirs, export_dir
from .result_levels import enrich_detection_row, iter_detection_items

LABEL_FONT_SCALE = 2.0


def _safe_stem(name: str) -> str:
    stem = Path(str(name or "image")).stem or "image"
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" ._")
    if safe.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        safe = f"{safe}_file"
    return safe[:80].rstrip(" ._") or "image"


def as_rgb_image(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return ImageOps.exif_transpose(image).convert("RGB")
    if isinstance(image, (str, Path)):
        with Image.open(image) as img:
            return ImageOps.exif_transpose(img).convert("RGB")
    array = np.asarray(image)
    if np.issubdtype(array.dtype, np.floating):
        array = np.nan_to_num(array, nan=0.0, posinf=255.0, neginf=0.0)
        if array.size and float(np.nanmax(array)) <= 1.0:
            array = array * 255.0
        array = np.clip(array, 0, 255).astype(np.uint8)
    return Image.fromarray(array).convert("RGB")


def label_font_for_image(image_size: tuple[int, int]) -> ImageFont.ImageFont:
    """Use a readable label font; model outputs do not control visual text size."""
    min_side = max(1, min(int(image_size[0]), int(image_size[1])))
    size = max(24, min(48, round(min_side / 70 * LABEL_FONT_SCALE)))
    candidates = [
        "msyh.ttc",
        "simhei.ttf",
        "arial.ttf",
        "DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def save_png_image(image: Any, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    as_rgb_image(image).save(output_path)
    return output_path


def save_result_image(image: Image.Image, storage_dir: str, image_name: str) -> Path:
    storage_root = ensure_app_dirs(storage_dir)
    output_dir = export_dir(str(storage_root)) / "result_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"检测结果图_{_safe_stem(image_name)}_{stamp}.png"
    counter = 1
    while path.exists():
        path = output_dir / f"检测结果图_{_safe_stem(image_name)}_{stamp}_{counter:02d}.png"
        counter += 1
    save_png_image(image, path)
    return path


def label_box_layout(
    image_width: int,
    image_height: int,
    anchor_x: float,
    anchor_y: float,
    text_width: int,
    text_height: int,
    *,
    pad_x: int = 4,
    pad_y: int = 3,
    gap: int = 6,
) -> tuple[int, int, int, int, int, int]:
    """Return a label background and text origin clamped inside the image."""
    box_width = max(1, int(text_width) + pad_x * 2)
    box_height = max(1, int(text_height) + pad_y * 2)
    max_left = max(0, int(image_width) - box_width)
    left = max(0, min(max_left, int(round(anchor_x))))

    above_top = int(round(anchor_y - box_height - gap))
    below_top = int(round(anchor_y + gap))
    if above_top >= 0:
        top = above_top
    elif below_top + box_height <= int(image_height):
        top = below_top
    else:
        top = 0
    max_top = max(0, int(image_height) - box_height)
    top = max(0, min(max_top, top))

    right = min(max(0, int(image_width) - 1), left + box_width)
    bottom = min(max(0, int(image_height) - 1), top + box_height)
    return left, top, right, bottom, left + pad_x, top + pad_y


def draw_detections_with_filter(
    image: Image.Image,
    detections: list[dict[str, Any]],
    visible_classes: list[str] | None = None,
) -> Image.Image:
    base = as_rgb_image(image)
    allowed = None if visible_classes is None else {str(item).strip() for item in visible_classes if str(item).strip()}
    annotated = base.copy()
    draw = ImageDraw.Draw(annotated)
    font = label_font_for_image(base.size)
    colors = {
        "龋齿": (235, 88, 60),
        "根尖周病变": (32, 146, 230),
        "阻生牙": (40, 170, 110),
    }
    width = max(2, round(min(base.size) / 300))

    for detection in iter_detection_items(detections):
        row = enrich_detection_row(detection, base.size)
        display_name = str(row.get("中文名称") or row.get("class") or "未知类别")
        if allowed is not None and display_name not in allowed and str(row.get("class") or "") not in allowed:
            continue
        try:
            x1 = float(row["x1"])
            y1 = float(row["y1"])
            x2 = float(row["x2"])
            y2 = float(row["y2"])
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            continue
        x1, x2 = sorted((max(0.0, min(base.width - 1, x1)), max(0.0, min(base.width - 1, x2))))
        y1, y2 = sorted((max(0.0, min(base.height - 1, y1)), max(0.0, min(base.height - 1, y2))))
        if x2 <= x1 or y2 <= y1:
            continue
        color = colors.get(display_name, (245, 174, 45))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=width)
        text = f"{display_name} {row.get('confidence', '')}"
        text_box = draw.textbbox((x1, y1), text, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        label_left, label_top, label_right, label_bottom, text_x, text_y = label_box_layout(
            base.width,
            base.height,
            x1,
            y1,
            text_w,
            text_h,
            pad_x=max(4, round(text_h * 0.35)),
            pad_y=max(3, round(text_h * 0.25)),
            gap=max(6, round(text_h * 0.35)),
        )
        draw.rectangle((label_left, label_top, label_right, label_bottom), fill=color)
        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
    return annotated


def crop_detection_regions(
    image: Image.Image,
    detections: list[dict[str, Any]],
    padding_ratio: float = 0.15,
) -> list[dict[str, Any]]:
    if image is None:
        return []
    pil_image = as_rgb_image(image)
    width, height = pil_image.size
    regions: list[dict[str, Any]] = []
    for index, detection in enumerate(iter_detection_items(detections), start=1):
        row = enrich_detection_row(detection, pil_image.size)
        try:
            x1 = float(row["x1"])
            y1 = float(row["y1"])
            x2 = float(row["x2"])
            y2 = float(row["y2"])
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            continue
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        if x2 <= x1 or y2 <= y1:
            continue
        pad_x = (x2 - x1) * padding_ratio
        pad_y = (y2 - y1) * padding_ratio
        left = max(0, int(round(x1 - pad_x)))
        top = max(0, int(round(y1 - pad_y)))
        right = min(width, int(round(x2 + pad_x)))
        bottom = min(height, int(round(y2 + pad_y)))
        if right <= left or bottom <= top:
            continue
        caption = (
            f"区域 {len(regions) + 1}：{row['中文名称']} | "
            f"置信度 {row['confidence']} | {row['关注等级']}"
            f"{' | ' + row['图像区域'] if row.get('图像区域') else ''}"
        )
        regions.append(
            {
                "image": pil_image.crop((left, top, right, bottom)),
                "caption": caption,
                "bbox": [left, top, right, bottom],
                "detection": row,
            }
        )
    return regions
