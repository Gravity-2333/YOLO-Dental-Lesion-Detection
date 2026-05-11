from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
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
            "class_id": self.cls_id,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
        }


class DentalDetector:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = YOLO(str(self.model_path))
        self.names = self.model.names

    def predict(
        self,
        image: Image.Image | np.ndarray,
        conf: float = 0.25,
        iou: float = 0.7,
        imgsz: int = 1024,
        device: str | int | None = None,
    ) -> tuple[Image.Image, list[Detection]]:
        pil_image = self._to_rgb_image(image)
        results = self.model.predict(
            source=np.array(pil_image),
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            verbose=False,
        )
        detections = self._parse_result(results[0])
        annotated = self._draw_detections(pil_image, detections)
        return annotated, detections

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
            return image.convert("RGB")
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
            draw.rectangle((det.x1, det.y1, det.x2, det.y2), outline=color, width=width)

            text = f"{det.label} {det.confidence:.2f}"
            text_box = draw.textbbox((det.x1, det.y1), text, font=font)
            text_w = text_box[2] - text_box[0]
            text_h = text_box[3] - text_box[1]
            label_y = max(0, det.y1 - text_h - 6)
            draw.rectangle(
                (det.x1, label_y, det.x1 + text_w + 8, label_y + text_h + 6),
                fill=color,
            )
            draw.text((det.x1 + 4, label_y + 3), text, fill=(255, 255, 255), font=font)

        return annotated


@lru_cache(maxsize=2)
def get_detector(model_path: str) -> DentalDetector:
    return DentalDetector(model_path)
