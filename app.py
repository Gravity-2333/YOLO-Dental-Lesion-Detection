from __future__ import annotations

import argparse
from pathlib import Path

import gradio as gr
import pandas as pd

from src.dental_detection.config import DEFAULT_MODEL_PATH
from src.dental_detection.inference import get_detector


def run_detection(image, conf: float, iou: float, imgsz: int, use_gpu: bool):
    if image is None:
        return None, [], {"错误": "请先上传一张图片。"}

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
    if rows:
        table = pd.DataFrame(
            [
                {
                    "类别ID": row["class_id"],
                    "类别": row["label"],
                    "置信度": row["confidence"],
                    "左上角X": row["x1"],
                    "左上角Y": row["y1"],
                    "右下角X": row["x2"],
                    "右下角Y": row["y2"],
                }
                for row in rows
            ],
            columns=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"],
        )
    else:
        table = pd.DataFrame(
            columns=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"],
        )
    summary = {
        "模型路径": str(DEFAULT_MODEL_PATH),
        "类别映射": {str(key): value for key, value in detector.names.items()},
        "检测数量": len(rows),
        "运行设备": "cuda:0" if use_gpu else "cpu",
    }
    return annotated, table, summary


def build_app() -> gr.Blocks:
    with gr.Blocks(title="YOLO 牙齿病变检测") as demo:
        gr.Markdown("# YOLO 牙齿病变检测")
        gr.Markdown("上传牙科影像，使用已训练的 YOLOv8 模型识别龋齿、根尖周病变和阻生牙区域。")

        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="pil", label="输入图片")
                with gr.Row():
                    conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度阈值")
                    iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU 阈值")
                with gr.Row():
                    imgsz = gr.Dropdown(
                        choices=[640, 768, 1024, 1280],
                        value=1024,
                        label="推理图片尺寸",
                    )
                    use_gpu = gr.Checkbox(value=True, label="使用 GPU")
                run_btn = gr.Button("开始检测", variant="primary")

            with gr.Column(scale=1):
                output = gr.Image(type="pil", label="检测结果图")
                detections = gr.Dataframe(
                    headers=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"],
                    label="检测结果表",
                    wrap=True,
                )
                summary = gr.JSON(label="检测摘要")

        run_btn.click(
            fn=run_detection,
            inputs=[image, conf, iou, imgsz, use_gpu],
            outputs=[output, detections, summary],
        )

    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动牙齿病变 YOLO Gradio 应用。")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", default=7860, type=int)
    parser.add_argument("--share", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    if not Path(DEFAULT_MODEL_PATH).exists():
        raise FileNotFoundError(f"模型文件不存在: {DEFAULT_MODEL_PATH}")
    args = parse_args()
    build_app().launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
    )
