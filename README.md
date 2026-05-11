# YOLO Dental Lesion Detection

基于 YOLOv8 的牙齿病变目标区域识别项目。当前版本提供一个 Gradio 原型界面，可上传牙科影像并输出检测框、类别和置信度。

## 当前模型

默认模型：

```text
models/dental_detect_12/weights/best.pt
```

类别：

```text
0: Caries
1: Periapical Lesion
2: Impacted
```

## 环境

推荐使用已有的 `yolo` mamba 环境：

```powershell
mamba activate yolo
python -m pip install -r requirements.txt
```

## 启动 Gradio

```powershell
mamba activate yolo
python app.py
```

默认访问：

```text
http://127.0.0.1:7860
```

## 检查模型

```powershell
mamba activate yolo
python scripts/check_model.py
```

## 项目结构

```text
assets/examples/              示例图片
data/                         数据集配置和本地数据占位
docs/AI_PROGRESS.md           AI 协作进度记录
experiments/                  历史训练或试跑输出
models/dental_detect_12/      当前牙科检测模型及训练结果
models/pretrained/            YOLO 官方预训练权重
scripts/                      工具脚本
src/dental_detection/         推理核心代码
app.py                        Gradio Web 应用入口
```

## 说明

`data/dental_lesion.yaml` 是后续训练用的数据集配置模板。真实牙科图片和标签默认不提交到 Git，以避免数据体积和隐私问题。
