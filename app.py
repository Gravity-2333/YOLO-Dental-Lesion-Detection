from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import gradio as gr
import pandas as pd
import torch

from src.dental_detection.config import DEFAULT_MODEL_NAME, MODEL_REGISTRY
from src.dental_detection.inference import Detection, get_detector

MODEL_SOURCE = "YOLOv8m 原始结构"
MODEL_OPTIMIZED = "YOLOv8m C2f-Faster-lite"
MODEL_COMPARE = "双模型对比"


def _empty_table() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"]
    )


def _table_from_detections(detections: Iterable[Detection]) -> pd.DataFrame:
    rows = [det.as_row() for det in detections]
    if not rows:
        return _empty_table()
    return pd.DataFrame(
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


def _detect_one(model_name: str, image, conf: float, iou: float, imgsz: int, device):
    model_info = MODEL_REGISTRY[model_name]
    detector = get_detector(str(model_info["path"]))
    annotated, detections = detector.predict(
        image=image,
        conf=conf,
        iou=iou,
        imgsz=int(imgsz),
        device=device,
    )
    return annotated, detections, detector.names


def run_detection(image, model_choice: str, conf: float, iou: float, imgsz: int, use_gpu: bool):
    if image is None:
        return None, _empty_table(), None, _empty_table(), {"错误": "请先上传一张图片。"}

    cuda_available = torch.cuda.is_available()
    if use_gpu and not cuda_available:
        raise gr.Error("当前 Python 环境没有可用 CUDA。请使用 mamba 的 yolo 环境启动应用。")
    device = 0 if use_gpu and cuda_available else "cpu"
    selected_models = (
        [MODEL_SOURCE, MODEL_OPTIMIZED] if model_choice == MODEL_COMPARE else [model_choice]
    )
    outputs = {
        MODEL_SOURCE: (None, _empty_table(), []),
        MODEL_OPTIMIZED: (None, _empty_table(), []),
    }
    class_names = {}

    for model_name in selected_models:
        annotated, detections, names = _detect_one(model_name, image, conf, iou, imgsz, device)
        outputs[model_name] = (annotated, _table_from_detections(detections), detections)
        class_names = {str(key): value for key, value in names.items()}

    summary = {
        "运行设备": "cuda:0" if device != "cpu" else "cpu",
        "GPU请求": bool(use_gpu),
        "CUDA可用": bool(cuda_available),
        "推理尺寸": int(imgsz),
        "置信度阈值": conf,
        "IoU阈值": iou,
        "类别映射": class_names,
        "模型": {
            name: {
                "路径": str(MODEL_REGISTRY[name]["path"]),
                "结构": MODEL_REGISTRY[name]["architecture"],
                "定位": MODEL_REGISTRY[name]["role"],
                "检测数量": len(outputs[name][2]),
                "test_mAP50": MODEL_REGISTRY[name]["metrics"]["test_mAP50"],
                "test_mAP50-95": MODEL_REGISTRY[name]["metrics"]["test_mAP50_95"],
                "Params": MODEL_REGISTRY[name]["metrics"]["params"],
                "GFLOPs": MODEL_REGISTRY[name]["metrics"]["gflops"],
            }
            for name in selected_models
        },
    }

    return (
        outputs[MODEL_SOURCE][0],
        outputs[MODEL_SOURCE][1],
        outputs[MODEL_OPTIMIZED][0],
        outputs[MODEL_OPTIMIZED][1],
        summary,
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="牙齿病变区域识别") as demo:
        gr.Markdown("# 牙齿病变区域识别")

        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="pil", label="输入影像", height=420)
                model_choice = gr.Radio(
                    choices=[MODEL_OPTIMIZED, MODEL_SOURCE, MODEL_COMPARE],
                    value=DEFAULT_MODEL_NAME,
                    label="模型",
                )
                with gr.Row():
                    conf = gr.Slider(0.05, 0.95, value=0.25, step=0.05, label="置信度")
                    iou = gr.Slider(0.1, 0.9, value=0.7, step=0.05, label="IoU")
                with gr.Row():
                    imgsz = gr.Dropdown(
                        choices=[640, 768, 1024, 1280],
                        value=1280,
                        label="尺寸",
                    )
                    use_gpu = gr.Checkbox(value=torch.cuda.is_available(), label="GPU")
                run_btn = gr.Button("检测", variant="primary")

            with gr.Column(scale=2):
                with gr.Row():
                    with gr.Column():
                        source_output = gr.Image(type="pil", label="YOLOv8m 原始结构", height=360)
                        source_table = gr.Dataframe(
                            headers=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"],
                            label="原始结构检测框",
                            wrap=True,
                        )
                    with gr.Column():
                        optimized_output = gr.Image(
                            type="pil", label="YOLOv8m C2f-Faster-lite", height=360
                        )
                        optimized_table = gr.Dataframe(
                            headers=["类别ID", "类别", "置信度", "左上角X", "左上角Y", "右下角X", "右下角Y"],
                            label="优化结构检测框",
                            wrap=True,
                        )
                summary = gr.JSON(label="摘要")

        run_btn.click(
            fn=run_detection,
            inputs=[image, model_choice, conf, iou, imgsz, use_gpu],
            outputs=[source_output, source_table, optimized_output, optimized_table, summary],
        )

    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动牙齿病变区域识别 Gradio 应用。")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", default=7860, type=int)
    parser.add_argument("--share", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    missing = [
        str(info["path"]) for info in MODEL_REGISTRY.values() if not Path(info["path"]).exists()
    ]
    if missing:
        raise FileNotFoundError("模型文件不存在: " + "; ".join(missing))
    args = parse_args()
    build_app().launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
    )
