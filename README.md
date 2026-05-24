# YOLO Dental Lesion Detection

基于 YOLOv8 的牙齿病变目标区域识别项目。当前版本提供一个 Gradio 界面，可上传牙科影像并输出检测框、类别和置信度。

## 当前模型

当前界面内置两个 YOLOv8m 候选模型：

| 模型 | 用途 | 权重 |
| --- | --- | --- |
| YOLOv8m 原始结构 | 高精度候选 | `models/final_candidates/yolov8m_1280_full/weights/best.pt` |
| YOLOv8m C2f-Faster-lite | 优化结构候选 | `models/final_candidates/yolov8m_c2f_faster_lite_1280_full/weights/best.pt` |

界面支持单模型检测和双模型对比。

类别：

```text
0: Caries
1: Periapical_Lesion
2: Impacted
```

`YOLOv8m C2f-Faster-lite` 权重依赖自定义 `C2fFasterLite` 模块。应用会优先加载同级工作区中的 `../yolov8-train` 源码，因此在当前目录结构下可以直接运行。

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
models/final_candidates/      YOLOv8m 最终候选模型权重和训练记录
models/configs/               自定义模型 yaml 备份
models/pretrained/            YOLO 官方预训练权重
scripts/                      工具脚本
src/dental_detection/         推理核心代码
app.py                        Gradio Web 应用入口
```

## 说明

`data/dental_lesion.yaml` 是后续训练用的数据集配置模板。真实牙科图片和标签默认不提交到 Git，以避免数据体积和隐私问题。
