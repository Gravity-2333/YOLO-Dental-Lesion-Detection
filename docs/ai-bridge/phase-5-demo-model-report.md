# 第五阶段演示模式与模型选择安全收口报告

更新时间：2026-07-09

## 1. 本阶段目标

本阶段目标是降低答辩演示时的误操作风险，尤其是误选 `last.pt`、预训练权重或早期实验权重，同时让检测工作台能看见当前模型状态，并把截图回归脚本整理为正式工具。

本阶段未训练模型，未修改权重，未提交 Git，未大规模拆分 `app.py`，未改变核心推理函数签名和既有输出组件顺序。

## 2. 修改文件列表

- `src/dental_detection/model_files.py`
- `src/dental_detection/model_info.py`
- `app.py`
- `assets/workbench.css`
- `scripts/capture_ui_screenshots.py`
- `docs/ai-bridge/runtime-logs/capture_phase4_screenshots.py`
- `README.md`
- `docs/文档索引.md`
- `docs/ai-bridge/phase-5-demo-model-report.md`
- `docs/ai-bridge/codex-to-chatgpt.md`
- `docs/ai-bridge/current-status.md`

## 3. 推荐模型 / 高级模型分层逻辑

新增模型分层 helper：

- `is_recommended_model_path(...)`
- `is_advanced_model_path(...)`
- `scan_model_files(..., include_advanced=False, recommended_paths=...)`

推荐模型默认包括：

1. `MODEL_REGISTRY` 明确登记的模型。
2. `models/final_candidates/**/weights/best.pt` 这类最终候选权重。

默认隐藏的高级模型包括：

1. `last.pt`
2. `epoch*.pt`
3. 预训练权重，例如 `yolov8n.pt`、`yolov8m.pt`
4. 早期实验目录、训练过程目录或未登记未知权重

设置页新增“显示高级模型 / 实验权重”选项，默认关闭。关闭时下拉框只显示推荐模型；开启时显示全部可扫描模型，并提示：

```text
高级模型可能包含实验权重、last.pt 或预训练模型，答辩演示请优先使用推荐模型。
```

当前验证结果：推荐列表只显示 baseline 与 C2f-Faster-lite 两个最终候选 `best.pt`，全部列表可扫描到 8 个模型文件。

## 4. 检测工作台模型状态提示实现方式

检测工作台顶部新增轻量模型状态块，显示：

- 当前演示模型
- 类型：`baseline` / `optimized` / `advanced / experimental`
- 是否推荐演示
- 是否依赖 `../yolov8-train`

该提示由 `_workbench_model_status_html(...)` 生成。完整模型卡片仍保留在设置页，工作台只显示轻量状态，避免页面过密。

## 5. 设置页演示推荐说明实现方式

设置页模型区域新增“推荐演示流程”说明：

1. 使用 baseline 模型作为稳定对照。
2. 使用 C2f-Faster-lite 优化模型展示改进效果。
3. 不建议在答辩中临时选择 `last.pt`、未知实验权重或预训练权重。

模型卡片新增“推荐用途”文案：

- baseline：稳定对照、兼容性高。
- C2f-Faster-lite：优化模型、展示改进效果，并说明依赖同级 `../yolov8-train`。
- 高级模型：仍可通过高级模型开关进入，但不作为默认演示入口。

## 6. UI 截图回归脚本整理情况

新增正式脚本：

```text
scripts/capture_ui_screenshots.py
```

支持参数：

```powershell
python scripts/capture_ui_screenshots.py --output docs/ai-bridge/screenshots/phase-5
python scripts/capture_ui_screenshots.py --base-url http://127.0.0.1:7860 --output outputs/ui-regression
```

能力：

- 默认访问 `http://127.0.0.1:7860`
- 支持 `--base-url`
- 支持 `--output`
- 支持系统 Chrome / Edge fallback
- 服务未启动时给出明确提示
- 覆盖工作台、模型下拉框、检测结果、AI 问答、病例记录、设置页和移动端工作台

旧脚本 `docs/ai-bridge/runtime-logs/capture_phase4_screenshots.py` 已改为调用新脚本，避免历史文档入口失效。

## 7. 文档更新情况

已更新 `README.md`：

- 补充推荐演示模型。
- 说明 baseline 与优化模型区别。
- 说明高级模型列表默认隐藏原因。
- 说明如何显示全部模型。
- 说明如何运行 UI 截图回归。

已更新 `docs/文档索引.md`：

- 增加 AI Bridge 阶段报告入口。
- 增加正式截图脚本入口。

## 8. 实际执行命令

```powershell
mamba run -n yolo python -m compileall app.py src\dental_detection scripts\capture_ui_screenshots.py docs\ai-bridge\runtime-logs\capture_phase4_screenshots.py
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
cmd.exe /c start_project.bat
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
mamba run -n yolo python scripts\capture_ui_screenshots.py --output docs\ai-bridge\screenshots\phase-5
git diff --check ...
```

## 9. 测试结果

| 命令 | 结果 |
| --- | --- |
| `compileall` | 通过 |
| `scripts/check_model.py` | 通过 |
| `test_bugs.py` | 通过，78 项测试 |
| `verify_optimization.py` | 通过 |
| `scripts/capture_ui_screenshots.py --output docs/ai-bridge/screenshots/phase-5` | 通过 |
| `git diff --check ...` | 通过，仅有 CRLF 提示 |

## 10. 服务启动结果

通过 `start_project.bat` 启动并确认服务可访问。

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`21352`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`
- 启动日志：未出现 `is not recognized` 或中文片段误执行问题。

## 11. 截图路径

第五阶段截图已保存到：

`docs/ai-bridge/screenshots/phase-5/`

文件：

- `01-workbench-home.png`
- `02-workbench-model-dropdown.png`
- `03-workbench-after-example-or-upload.png`
- `04-ai-chat.png`
- `05-cases.png`
- `06-settings.png`
- `07-mobile-workbench.png`

## 12. 剩余问题

1. 设置页高级模型开关目前是会话级 UI 选项，未持久化到用户配置；这是刻意保守处理，避免演示机器下次打开时默认显示实验权重。
2. 检测工作台只展示轻量模型状态，没有把完整模型卡片搬入工作台；若用户希望“工作台直接切模型”，需要下一阶段再评估。
3. `app.py` 仍较大，本阶段按要求只做小步安全收口，没有结构性拆分。

## 13. 是否建议进入第六阶段代码结构优化

建议进入第六阶段，但仍建议小步推进：

1. 优先抽离模型展示与模型选择状态 helper。
2. 再考虑导出逻辑或 UI 文案常量拆分。
3. 保持 `test_bugs.py`、`check_model.py` 和 UI 截图回归作为准入验证。
4. 不改变推理函数签名和 Gradio 输出组件顺序。
