# 第六阶段模型展示与 UI 状态 helper 小步结构优化报告

更新时间：2026-07-09

## 1. 本阶段目标

本阶段按 `docs/ai-bridge/chatgpt-to-codex.md` 执行，只做模型展示与 UI 状态 helper 的小步抽离，降低 `app.py` 继续膨胀的风险。

本阶段未训练模型，未修改权重，未提交 Git，未改变核心推理函数签名，未改变 Gradio 输出组件顺序，未移动导出、AI 问答或病例主流程。

## 2. 审计结论

审计记录已生成：

`docs/ai-bridge/phase-6-refactor-audit.md`

模型卡片 HTML、工作台模型状态 HTML、推荐演示说明、高级模型提示和模型路径紧凑显示属于纯展示逻辑，可以安全抽离；`refresh_model_choices()`、`apply_model_card()`、`_current_model_info_markdown()` 仍与 Gradio 更新对象和事件输出顺序强耦合，本阶段保留在 `app.py`。

## 3. 修改文件列表

- `src/dental_detection/model_ui.py`
- `src/dental_detection/model_info.py`
- `app.py`
- `test_bugs.py`
- `docs/文档索引.md`
- `docs/ai-bridge/phase-6-refactor-audit.md`
- `docs/ai-bridge/phase-6-model-ui-refactor-report.md`
- `docs/ai-bridge/codex-to-chatgpt.md`
- `docs/ai-bridge/current-status.md`

## 4. 新增 helper 模块说明

新增 `src/dental_detection/model_ui.py`，提供以下纯展示函数：

- `format_model_path_for_display(...)`
- `build_model_path_compact_html(...)`
- `build_advanced_model_warning_html()`
- `build_demo_recommendation_html()`
- `build_model_cards_html(...)`
- `build_workbench_model_status_html(...)`

这些函数不依赖 Gradio 组件，不加载模型，不扫描模型文件，只消费外部传入的模型卡片、路径和推荐路径集合。

## 5. 从 app.py 抽离的逻辑

- 设置页模型卡片 HTML 构建逻辑。
- 检测工作台当前模型轻量状态块。
- 推荐演示流程说明。
- 高级模型风险提示。
- 模型路径省略显示和完整路径 `title` 保留。

`app.py` 现在只保留 Gradio 事件绑定、组件输出顺序和模型选择状态协调。

## 6. 暂未抽离的逻辑与原因

- `refresh_model_choices()`：直接返回 `gr.update(...)`，与 Gradio 状态更新耦合。
- `apply_model_card()`：输出数量和顺序敏感，贸然外移容易引发 UI 回归。
- `_current_model_info_markdown()`：同时处理注册模型和自定义路径，仍贴近设置页事件。
- `_recommended_model_paths()`：函数很小，依赖 `MODEL_REGISTRY`，留在 `app.py` 更直观。

## 7. 测试新增或调整情况

扩展 `test_bugs.py`，新增第 79 项测试：

- baseline 状态 HTML 包含“稳定对照”。
- C2f-Faster-lite 状态 HTML 包含 `../yolov8-train`。
- 高级模型状态 HTML 包含“不建议答辩临时使用”。
- 长路径展示会省略，同时保留完整 `title`。
- 推荐演示说明和高级模型提示不为空。

## 8. 实际执行命令

```powershell
mamba run -n yolo python -m compileall app.py src\dental_detection scripts
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
mamba run -n yolo python -c "import app; app.build_app(); print('build_app ok')"
cmd.exe /c start_project.bat
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
mamba run -n yolo python scripts\capture_ui_screenshots.py --output docs\ai-bridge\screenshots\phase-6
git diff --check -- app.py src\dental_detection\model_info.py src\dental_detection\model_ui.py test_bugs.py docs\文档索引.md docs\ai-bridge\phase-6-refactor-audit.md
```

## 9. 测试结果

| 命令 | 结果 |
| --- | --- |
| `compileall` | 通过 |
| `scripts/check_model.py` | 通过，默认 C2f-Faster-lite 模型可加载 |
| `test_bugs.py` | 通过，79 项测试完成 |
| `verify_optimization.py` | 通过 |
| `app.build_app()` | 通过 |
| `git diff --check ...` | 通过，仅有 CRLF 提示 |

## 10. 服务启动结果

通过 `start_project.bat` 启动并确认服务可访问。

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`19560`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`
- 启动日志：未出现 `is not recognized` 或中文片段误执行问题。

## 11. 截图路径

第六阶段截图已保存到：

`docs/ai-bridge/screenshots/phase-6/`

文件：

- `01-workbench-home.png`
- `02-workbench-model-dropdown.png`
- `03-workbench-after-example-or-upload.png`
- `04-ai-chat.png`
- `05-cases.png`
- `06-settings.png`
- `07-mobile-workbench.png`

## 12. 剩余问题

1. `app.py` 仍然较大，但本阶段按边界只抽离模型展示相关 helper。
2. `refresh_model_choices()` 和 `apply_model_card()` 仍在 `app.py`，后续若要外移，需要先设计稳定的 UI 更新对象边界。
3. 截图回归仍是手动命令执行，暂未纳入 CI 或一键验证脚本。

## 13. 是否建议进入第七阶段

建议进入第七阶段，但继续小步推进。优先方向可二选一：

1. 导出逻辑抽离：把 ZIP / HTML / CSV 组织从 `app.py` 迁到专门模块。
2. UI 文案常量抽离：把重复中文提示整理为低风险常量模块。

如果进入导出逻辑抽离，建议先只处理纯文件组织 helper，不改报告内容和导出按钮输出顺序。
