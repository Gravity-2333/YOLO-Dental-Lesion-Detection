from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .assistant import ensure_app_dirs, export_dir
from .result_levels import enrich_detection_row


def _safe_stem(name: str) -> str:
    safe = "".join("_" if char in '<>:"/\\|?*\x00' else char for char in str(name or "image")).strip(" ._")
    return (Path(safe).stem or "image")[:80].rstrip(" ._") or "image"


def save_result_image(image: Image.Image, storage_dir: str, image_name: str) -> Path:
    storage_root = ensure_app_dirs(storage_dir)
    output_dir = export_dir(str(storage_root)) / "result_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{stamp}_{_safe_stem(image_name)}_检测结果.png"
    counter = 1
    while path.exists():
        path = output_dir / f"{stamp}_{_safe_stem(image_name)}_检测结果_{counter:02d}.png"
        counter += 1
    ImageOps.exif_transpose(image).convert("RGB").save(path)
    return path


def crop_detection_regions(
    image: Image.Image,
    detections: list[dict[str, Any]],
    padding_ratio: float = 0.15,
) -> list[dict[str, Any]]:
    if image is None:
        return []
    pil_image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = pil_image.size
    regions: list[dict[str, Any]] = []
    for index, detection in enumerate(detections or [], start=1):
        row = enrich_detection_row(detection)
        try:
            x1 = float(row["x1"])
            y1 = float(row["y1"])
            x2 = float(row["x2"])
            y2 = float(row["y2"])
        except (TypeError, ValueError):
            continue
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
