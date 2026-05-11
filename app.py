from __future__ import annotations

import argparse
from pathlib import Path

import gradio as gr
import pandas as pd

from src.dental_detection.config import DEFAULT_MODEL_PATH
from src.dental_detection.inference import get_detector


def run_detection(image, conf: float, iou: float, imgsz: int, use_gpu: bool):
    if image is None:
        return None, [], {"error": "Please upload an image first."}

    device = 0 if use_gpu else "cpu"
    detector = get_detector(str(DEFAULT_MODEL_PATH))
    annotated, detections = detector.predict(
        image=image,
        conf=conf,
        iou=iou,
        imgsz=int(imgsz),
        device=device,
    )
    rows = [det.as_row() for det in detections]
    table = pd.DataFrame(
        rows,
        columns=["class_id", "label", "confidence", "x1", "y1", "x2", "y2"],
    )
    summary = {
        "model": str(DEFAULT_MODEL_PATH),
        "classes": detector.names,
        "count": len(rows),
        "device": "cuda:0" if use_gpu else "cpu",
    }
    return annotated, table, summary


def build_app() -> gr.Blocks:
    with gr.Blocks(title="YOLO Dental Lesion Detection") as demo:
        gr.Markdown("# YOLO Dental Lesion Detection")
        gr.Markdown("Upload a dental image and run the trained YOLOv8 detector.")

        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="pil", label="Input image")
                with gr.Row():
                    conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="Confidence")
                    iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU")
                with gr.Row():
                    imgsz = gr.Dropdown(
                        choices=[640, 768, 1024, 1280],
                        value=1024,
                        label="Image size",
                    )
                    use_gpu = gr.Checkbox(value=True, label="Use GPU")
                run_btn = gr.Button("Run detection", variant="primary")

            with gr.Column(scale=1):
                output = gr.Image(type="pil", label="Annotated image")
                detections = gr.Dataframe(
                    headers=["class_id", "label", "confidence", "x1", "y1", "x2", "y2"],
                    label="Detections",
                    wrap=True,
                )
                summary = gr.JSON(label="Summary")

        run_btn.click(
            fn=run_detection,
            inputs=[image, conf, iou, imgsz, use_gpu],
            outputs=[output, detections, summary],
        )

    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the dental YOLO Gradio app.")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", default=7860, type=int)
    parser.add_argument("--share", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    if not Path(DEFAULT_MODEL_PATH).exists():
        raise FileNotFoundError(f"Model not found: {DEFAULT_MODEL_PATH}")
    args = parse_args()
    build_app().launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
    )
