# 当前分支运行说明：原始 YOLOv8 基线

本分支：`main`

配套 YOLOv8 源码分支：`../yolo8` 的 `main` 或官方未改动源码。

本分支用于训练原始 YOLOv8 基线模型，不加入 P2、EMA、DySample。建议分别训练 `n/s/m` 三个模型，用于和后续改进分支做对比。

## 数据集

数据集已复制到：

```text
data/dental_lesion
```

当前配置文件：

```text
data/dental_lesion.yaml
```

包含 532 张训练图、132 张验证图，并使用 3 个类别：`Caries`、`Periapical Lesion`、`Impacted`。

## 环境准备

```powershell
mamba run -n yolo python -m pip install -e ../yolo8
mamba run -n yolo python -c "import ultralytics, pathlib; print(ultralytics.__version__); print(pathlib.Path(ultralytics.__file__).resolve())"
```

如果想完全使用 pip 安装版 ultralytics，也可以不执行 editable 安装；但为了本项目路径统一，推荐仍使用 `../yolo8/main`。

## 旧模型检查

```powershell
mamba run -n yolo python scripts/check_model.py
```

该命令会检查当前已有 baseline 权重：

```text
models/dental_detect_12/weights/best.pt
```

## 本地极小训练测试

只验证链路：

```powershell
mamba run -n yolo yolo detect train model=models/pretrained/yolov8n.pt data=data/dental_lesion.yaml epochs=1 imgsz=320 batch=1 device=0 workers=0 project=runs/detect name=dental_yolov8n_baseline_smoke
```

如果重新打包到服务器，确认 `data/dental_lesion/images/train` 和 `data/dental_lesion/images/val` 一起上传。

## 云服务器正式训练：YOLOv8n

```bash
mamba activate yolo
yolo detect train model=models/pretrained/yolov8n.pt data=data/dental_lesion.yaml epochs=200 imgsz=640 batch=16 device=0 workers=8 project=runs/detect name=dental_yolov8n_baseline
```

## 云服务器正式训练：YOLOv8s

先准备 `models/pretrained/yolov8s.pt`，再运行：

```bash
mamba activate yolo
yolo detect train model=models/pretrained/yolov8s.pt data=data/dental_lesion.yaml epochs=200 imgsz=640 batch=16 device=0 workers=8 project=runs/detect name=dental_yolov8s_baseline
```

如果没有本地权重，也可让 Ultralytics 自动下载：

```bash
yolo detect train model=yolov8s.pt data=data/dental_lesion.yaml epochs=200 imgsz=640 batch=16 device=0 workers=8 project=runs/detect name=dental_yolov8s_baseline
```

## 云服务器正式训练：YOLOv8m

先准备 `models/pretrained/yolov8m.pt`，再运行：

```bash
mamba activate yolo
yolo detect train model=models/pretrained/yolov8m.pt data=data/dental_lesion.yaml epochs=200 imgsz=640 batch=8 device=0 workers=8 project=runs/detect name=dental_yolov8m_baseline
```

如果没有本地权重，也可让 Ultralytics 自动下载：

```bash
yolo detect train model=yolov8m.pt data=data/dental_lesion.yaml epochs=200 imgsz=640 batch=8 device=0 workers=8 project=runs/detect name=dental_yolov8m_baseline
```

## 推理和展示

训练完成后，权重通常位于：

```text
runs/detect/dental_yolov8n_baseline/weights/best.pt
runs/detect/dental_yolov8s_baseline/weights/best.pt
runs/detect/dental_yolov8m_baseline/weights/best.pt
```

单模型 Gradio：

```powershell
mamba run -n yolo python app.py
```

多模型对比展示请使用 `feat/gradio-comparison-dashboard` 分支。
