# YOLO Dental Lesion Detection

基于 YOLOv8 的牙齿病变目标区域识别项目。当前版本提供一个 Gradio 检测工作台，可上传单张或多张牙科影像，输出原图、实际入模图、检测结果图、检测框表格和辅助建议。

## 当前模型

当前界面内置两个 YOLOv8m 候选模型：

| 模型 | 用途 | 权重 |
| --- | --- | --- |
| YOLOv8m 原始结构 | 高精度候选 | `models/final_candidates/yolov8m_1280_full/weights/best.pt` |
| YOLOv8m C2f-Faster-lite | 优化结构候选 | `models/final_candidates/yolov8m_c2f_faster_lite_1280_full/weights/best.pt` |

界面支持单模型检测、双模型对比选项、批量图片逐张查看，以及低对比度牙片的可选 CLAHE 增强推理。

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

## 前端功能

- 单张图片拖拽上传后，可再次拖拽新图片直接替换原图片。
- 批量上传多张图片后，可在下拉列表中逐张查看原始上传图、实际送入模型的图、检测结果图和检测框表格。
- 默认推理只做 EXIF 方向修正、RGB 转换和 `numpy.uint8` 格式化，不强制增强。
- 可勾选“使用 CLAHE 增强后推理（适合低对比度牙片）”，执行灰度、轻微高斯模糊、CLAHE、RGB 三通道转换后再送入 YOLO。
- 检测框表格字段为 `class`、`confidence`、`x1`、`y1`、`x2`、`y2`。

## AI 建议与对话

- AI 功能关闭时，界面根据检测类别、数量、置信度和框位置生成内置默认建议。
- AI 功能开启时，使用 OpenAI-compatible Chat Completions 协议，固定调用 `/v1/chat/completions`。
- 第一版请求字段只使用 `model`、`messages`、`temperature`、`max_tokens`，不使用 Responses API、tools、function calling、reasoning 或持久化接口字段。
- 测试接口按钮发送极小请求：`请只回复 OK`、`temperature=0`、`max_tokens=8`。
- 第一版不会把牙片图片发送给 AI，只发送检测类别、数量、置信度、检测框位置和安全提示词。
- AI 建议和内置建议均为辅助参考，不能替代专业牙科医生诊断；不输出最终诊断、不提供处方、不提供具体药物剂量。

## 本地配置和记录

- 用户配置和对话记录保存在用户目录下的 `YOLO-Dental-Lesion-Detection` 文件夹中。
- 默认对话目录为 `Path.home() / "YOLO-Dental-Lesion-Detection" / "conversations"`。
- 环境变量模式下，API Key 输入框填写环境变量名，配置文件只保存环境变量名。
- 直接 Key 值模式下，默认不保存真实 Key；只有勾选“保存 API Key 到本地配置”时才写入用户目录配置文件。
- 公网 HTTPS API 地址缺少 Key 时不会发起请求；本地或局域网接口允许空 Key 或占位 Key。

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
