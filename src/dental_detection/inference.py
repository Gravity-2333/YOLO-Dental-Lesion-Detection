from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import CUSTOM_ULTRALYTICS_PATH

if CUSTOM_ULTRALYTICS_PATH.exists():
    sys.path.insert(0, str(CUSTOM_ULTRALYTICS_PATH))

from ultralytics import YOLO


@dataclass(frozen=True)
class Detection:
    cls_id: int
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def as_row(self) -> dict[str, Any]:
        return {
            "class": self.label,
            "confidence": round(self.confidence, 4),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
        }


MAX_IMAGE_PIXELS = 8000 * 8000  # 最大像素数，超过此值先等比例缩放


def _normalized_rgb_image(image: Image.Image | np.ndarray | str | Path) -> Image.Image:
    """Normalize user input for YOLO without changing aspect ratio."""
    if isinstance(image, Image.Image):
        pil_image = ImageOps.exif_transpose(image).convert("RGB")
    elif isinstance(image, (str, Path)):
        with Image.open(image) as img:
            pil_image = ImageOps.exif_transpose(img).convert("RGB")
    else:
        pil_image = ImageOps.exif_transpose(Image.fromarray(np.asarray(image))).convert("RGB")

    # 超大图像先等比例缩放，避免内存暴涨
    w, h = pil_image.size
    pixels = w * h
    if pixels > MAX_IMAGE_PIXELS:
        scale = (MAX_IMAGE_PIXELS / pixels) ** 0.5
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
    return pil_image


def preprocess_image(image: Image.Image | np.ndarray | str | Path, use_clahe: bool = False) -> np.ndarray:
    rgb = np.asarray(_normalized_rgb_image(image), dtype=np.uint8)
    if not use_clahe:
        return rgb

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)


class DentalDetector:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = YOLO(str(self.model_path))
        self.names = self.model.names

    def predict(
        self,
        image: Image.Image | np.ndarray | str | Path,
        use_clahe: bool = False,
        conf: float = 0.25,
        iou: float = 0.7,
        imgsz: int = 1280,
        device: str | int | None = None,
    ) -> tuple[Image.Image, Image.Image, Image.Image, list[Detection]]:
        normalized_image = _normalized_rgb_image(image)
        original_array = np.asarray(normalized_image, dtype=np.uint8)
        # CLAHE 关闭时复用 original_array，避免重复的 EXIF transpose + RGB 转换
        if use_clahe:
            model_array = preprocess_image(normalized_image, use_clahe=True)
        else:
            model_array = original_array
        results = self.model.predict(
            source=model_array,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            verbose=False,
        )
        detections = self._parse_result(results[0])
        model_image = Image.fromarray(model_array)
        annotated = self._draw_detections(model_image, detections)
        return Image.fromarray(original_array), model_image, annotated, detections

    def _parse_result(self, result: Any) -> list[Detection]:
        detections: list[Detection] = []
        if result.boxes is None:
            return detections

        for box in result.boxes:
            cls_id = int(box.cls.item())
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    cls_id=cls_id,
                    label=str(self.names.get(cls_id, cls_id)),
                    confidence=float(box.conf.item()),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return detections

    @staticmethod
    def _to_rgb_image(image: Image.Image | np.ndarray) -> Image.Image:
        if isinstance(image, Image.Image):
            return ImageOps.exif_transpose(image).convert("RGB")
        if isinstance(image, (str, Path)):
            with Image.open(image) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
        return Image.fromarray(np.asarray(image)).convert("RGB")

    @staticmethod
    def _draw_detections(image: Image.Image, detections: list[Detection]) -> Image.Image:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        font = ImageFont.load_default()
        colors = {
            0: (235, 88, 60),
            1: (32, 146, 230),
            2: (40, 170, 110),
        }

        for det in detections:
            color = colors.get(det.cls_id, (245, 174, 45))
            width = max(2, round(min(image.size) / 300))
            x1, x2 = sorted((float(det.x1), float(det.x2)))
            y1, y2 = sorted((float(det.y1), float(det.y2)))
            x1 = max(0.0, min(float(image.width - 1), x1))
            x2 = max(0.0, min(float(image.width - 1), x2))
            y1 = max(0.0, min(float(image.height - 1), y1))
            y2 = max(0.0, min(float(image.height - 1), y2))
            if x2 <= x1 or y2 <= y1:
                continue
            draw.rectangle((x1, y1, x2, y2), outline=color, width=width)

            text = f"{det.label} {det.confidence:.2f}"
            text_box = draw.textbbox((x1, y1), text, font=font)
            text_w = text_box[2] - text_box[0]
            text_h = text_box[3] - text_box[1]
            label_y = max(0, y1 - text_h - 6)
            draw.rectangle(
                (x1, label_y, min(image.width - 1, x1 + text_w + 8), label_y + text_h + 6),
                fill=color,
            )
            draw.text((x1 + 4, label_y + 3), text, fill=(255, 255, 255), font=font)

        return annotated


@lru_cache(maxsize=2)
def get_detector(model_path: str) -> DentalDetector:
    return DentalDetector(model_path)


def run_inference(
    image: Image.Image | np.ndarray | str | Path,
    model_path: str | Path,
    use_clahe: bool = False,
    conf: float = 0.25,
    iou: float = 0.7,
    imgsz: int = 1280,
    device: str | int | None = None,
) -> tuple[Image.Image, Image.Image, Image.Image, list[Detection], dict[int, str]]:
    detector = get_detector(str(model_path))
    original, model_input, annotated, detections = detector.predict(
        image=image,
        use_clahe=use_clahe,
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        device=device,
    )
    return original, model_input, annotated, detections, detector.names
