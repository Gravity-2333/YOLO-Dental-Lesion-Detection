# YOLO Dental Lesion Detection

基于 YOLOv8 的牙齿病变目标区域识别项目。当前版本提供一个 Gradio 检测工作台，可上传单张或多张牙科影像，输出原图、实际入模图、检测结果图、检测框表格和辅助建议。

## 当前模型

当前界面内置两个 YOLOv8m 候选模型：

| 模型 | 用途 | 权重 |
| --- | --- | --- |
| YOLOv8m 原始结构 | baseline，稳定对照，兼容性高 | `models/final_candidates/yolov8m_1280_full/weights/best.pt` |
| YOLOv8m C2f-Faster-lite | 优化模型，展示结构改进效果 | `models/final_candidates/yolov8m_c2f_faster_lite_1280_full/weights/best.pt` |

界面支持单模型检测、双模型对比选项、批量图片逐张查看，以及低对比度牙片的可选 CLAHE 增强推理。

类别：

```text
0: Caries
1: Periapical_Lesion
2: Impacted
```

`YOLOv8m C2f-Faster-lite` 权重依赖自定义 `C2fFasterLite` 模块。应用会优先加载同级工作区中的 `../yolov8-train` 源码，因此在当前目录结构下可以直接运行。

## 答辩演示建议

推荐演示流程：

1. 先使用 `YOLOv8m 原始结构` 作为 baseline，展示系统基础识别流程。
2. 再切换到 `YOLOv8m C2f-Faster-lite`，展示优化模型效果。
3. 如需对照，可在设置页开启对比模型模式。

设置页的高级模型路径默认只显示推荐模型，避免误选 `last.pt`、预训练权重或早期实验权重。确实需要复现实验时，可勾选“显示高级模型 / 实验权重”查看全部可扫描模型；答辩演示请优先使用推荐模型卡片。

如果迁移项目到其他机器，优化模型需要同时保留同级目录：

```text
../yolov8-train
```

若该目录缺失，建议先使用 baseline 模型完成演示。

## 环境

推荐使用已有的 `yolo` mamba 环境：

```powershell
mamba activate yolo
python -m pip install -r requirements.txt
```

## 启动 Gradio

推荐直接使用项目脚本：

```powershell
.\start_project.bat
```

脚本会先检查当前端口上是否已有本项目进程；如果已有，会先自动关闭再重新启动。参数集中在 `scripts/project_config.bat`，可在其中修改端口、地址、mamba 环境名或 Python 路径。

关闭项目：

```powershell
.\stop_project.bat
```

关闭脚本会先检查是否存在可关闭的项目进程，存在时才执行关闭。

也可以手动启动：

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
- 上传图片后会显示轻量图像质量提示，包括尺寸、亮度、对比度和可能的低质量输入风险；该提示只用于提醒，不会改变默认推理图像。
- 检测完成后可导出当前单图报告 ZIP，包含 `report.html`、三张结果图、检测表 CSV/JSON、建议文本和摘要文本。
- “病例记录”页可把当前检测摘要、检测框和建议保存为病例记录 JSON；默认不保存原始牙片图片。

## AI 建议与对话

- AI 功能关闭时，界面根据检测类别、数量、置信度和框位置生成内置默认建议。
- AI 接口默认使用 DeepSeek OpenAI-compatible 配置：`https://api.deepseek.com/v1`、`deepseek-chat`、环境变量名 `DEEPSEEK_API_KEY`。
- AI 功能开启时，使用 OpenAI-compatible Chat Completions 协议，固定调用 `/v1/chat/completions`。
- 第一版请求字段只使用 `model`、`messages`、`temperature`、`max_tokens`，不使用 Responses API、tools、function calling、reasoning 或持久化接口字段。
- 测试接口按钮发送极小请求：`请只回复 OK`、`temperature=0`、`max_tokens=8`。
- 第一版不会把牙片图片发送给 AI，只发送检测类别、数量、置信度、检测框位置和安全提示词。
- AI 建议和内置建议均为辅助参考，不能替代专业牙科医生诊断；不输出最终诊断、不提供处方、不提供具体药物剂量。

## 本地配置和记录

- 用户配置和对话记录保存在用户目录下的 `YOLO-Dental-Lesion-Detection` 文件夹中。
- 默认对话目录为 `Path.home() / "YOLO-Dental-Lesion-Detection" / "conversations"`。
- 批量导出、单图报告和病例记录默认分别保存在同一数据根目录下的 `exports/`、`reports/`、`cases/`。
- 环境变量模式下，API Key 输入框填写环境变量名，配置文件只保存环境变量名。
- 直接 Key 值模式下，默认不保存真实 Key；只有勾选“保存 API Key 到本地配置”时才写入用户目录配置文件。
- 公网 HTTPS API 地址缺少 Key 时不会发起请求；本地或局域网接口允许空 Key 或占位 Key。

## 检查模型

```powershell
mamba activate yolo
python scripts/check_model.py
```

## 展示前检查

答辩或演示前可运行一键检查：

```powershell
python scripts/pre_demo_check.py
```

如需同时生成截图回归：

```powershell
python scripts/pre_demo_check.py --with-screenshots --screenshot-output outputs/ui-regression
```

该检查会先运行 `tests/` 中的模块化单元测试，再执行模型、兼容回归和综合检查。

也可以只检查新抽离的 helper：

```powershell
python scripts/check_model_ui_helpers.py
python scripts/check_export_helpers.py
```

## UI 截图回归

启动服务后，可运行正式截图脚本生成回归截图：

```powershell
mamba activate yolo
python scripts/capture_ui_screenshots.py --output outputs/ui-regression
```

默认访问 `http://127.0.0.1:7860`。如需指定地址：

```powershell
python scripts/capture_ui_screenshots.py --base-url http://127.0.0.1:7860 --output outputs/ui-regression
```

## 前端样式开发

运行时样式由 `src/dental_detection/ui_assets.py` 按固定顺序加载，样式文件位于 `assets/styles/`：

```text
00-tokens.css       颜色、间距、圆角和阴影设计变量
10-foundation.css   页面基础样式、标题和主导航
20-layout.css       工作台、卡片和页面区域布局
30-components.css   模型卡片、按钮、表格、输入控件等组件
40-responsive.css   桌面/移动端响应式规则
50-utilities.css    Gradio 兼容修正、状态和辅助效果
```

调整整体风格时优先修改设计变量；新增组件样式放入 `30-components.css`，不要继续向兼容入口 `assets/workbench.css` 堆叠规则。

## 代码模块约定

- `settings_store.py` 只负责本地设置、应用目录和存储迁移。
- `ai_client.py` 只负责 OpenAI-compatible 地址、鉴权和请求。
- `advice.py` 负责检测结果提示词和离线建议。
- `conversation_store.py` 负责对话记录持久化。
- `assistant.py` 是旧导入路径的兼容入口；新增代码应直接导入上述职责模块。
- `ui_contracts.py` 定义 Gradio 主流程输出顺序，新增或删除公共输出时必须同步更新契约和测试。
- `ui_content.py` 集中维护页面标题、说明和安全文案，`ui_constants.py` 保存模型模式与检测表字段契约。
- `gradio_files.py` 集中管理导出文件白名单、下载组件状态和存储目录校验。

## 项目结构

```text
assets/examples/              示例图片
assets/styles/                模块化前端样式
data/                         数据集配置和本地数据占位
docs/文档索引.md              项目文档索引
docs/项目进度/                AI 协作进度、任务总结和优化变更日志
docs/修复记录/                Bug 清单、修复记录和完整修复总结
docs/界面优化/                前端界面、按钮对齐、字体和下拉框优化记录
docs/数据集审计/              数据集审计报告和摘要
docs/协作规范/                Git、分支和协作规范
docs/归档资料/                旧版目录树和历史资料
experiments/                  历史训练或试跑输出
models/dental_detect_12/      当前牙科检测模型及训练结果
models/final_candidates/      YOLOv8m 最终候选模型权重和训练记录
models/configs/               自定义模型 yaml 备份
models/pretrained/            YOLO 官方预训练权重
scripts/                      工具脚本
src/dental_detection/         推理核心代码
tests/                        可独立运行的标准库单元测试
app.py                        Gradio Web 应用入口
```

## 说明

`data/dental_lesion.yaml` 是后续训练用的数据集配置模板。真实牙科图片和标签默认不提交到 Git，以避免数据体积和隐私问题。
