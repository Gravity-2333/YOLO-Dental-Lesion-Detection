# 第八阶段测试体系整理与一键展示前检查报告

更新时间：2026-07-10

## 1. 本阶段目标

本阶段按 `docs/ai-bridge/chatgpt-to-codex.md` 执行，目标是整理测试入口、独立新 helper 检查脚本，并新增答辩前一键检查脚本。

本阶段未训练模型，未修改权重，未提交 Git，未大规模拆分 `app.py`，未改变业务功能、核心推理函数签名、Gradio 输出组件顺序或 UI 行为。

## 2. 测试入口审计结论

审计记录已生成：

`docs/ai-bridge/phase-8-test-audit.md`

结论是：

- `test_bugs.py` 仍是历史兼容主入口，目前 80 项测试覆盖面广，但定位效率会随规模下降。
- 第六、第七阶段新增 helper 的测试适合独立成轻量脚本，便于快速定位。
- `scripts/check_model.py`、新 helper 检查脚本、`test_bugs.py`、`verify_optimization.py` 组成默认展示前最小检查链路。
- 截图回归仍作为可选检查，需要 Gradio 服务已启动。

## 3. 修改文件列表

- `scripts/check_model_ui_helpers.py`
- `scripts/check_export_helpers.py`
- `scripts/pre_demo_check.py`
- `README.md`
- `docs/文档索引.md`
- `docs/ai-bridge/phase-8-test-audit.md`
- `docs/ai-bridge/phase-8-test-system-report.md`
- `docs/ai-bridge/codex-to-chatgpt.md`
- `docs/ai-bridge/current-status.md`

## 4. 新增脚本说明

### `scripts/check_model_ui_helpers.py`

用于独立检查 `src/dental_detection/model_ui.py`：

- baseline 状态 HTML 包含“稳定对照”。
- C2f-Faster-lite 状态 HTML 包含 `../yolov8-train`。
- 高级模型状态 HTML 包含“不建议答辩临时使用”。
- 长路径展示会省略，并保留完整 `title`。
- 推荐演示说明和高级模型警告不为空。

成功输出：

```text
PASS check_model_ui_helpers
```

### `scripts/check_export_helpers.py`

用于独立检查 `src/dental_detection/exporters.py`：

- 安全文件名处理空值、中文、特殊字符和 Windows 保留名。
- CSV 写入保留公式注入防护。
- JSON 写入保留中文。
- HTML 使用 UTF-8 写入。
- ZIP manifest 包含预期文件。
- 缺失文件加入 ZIP 时安全跳过并记录 skipped。
- 临时目录清理逻辑可正常执行。

成功输出：

```text
PASS check_export_helpers
```

### `scripts/pre_demo_check.py`

用于答辩或展示前一键检查。默认执行：

- `scripts/check_model.py`
- `scripts/check_model_ui_helpers.py`
- `scripts/check_export_helpers.py`
- `test_bugs.py`
- `verify_optimization.py`

支持：

- `--skip-slow`：跳过 `test_bugs.py` 和 `verify_optimization.py`。
- `--with-screenshots`：额外执行截图回归。
- `--screenshot-output`：指定截图目录。
- `--base-url`：指定 Gradio 服务地址。

脚本使用当前 Python 解释器执行子命令，不硬编码 mamba。

## 5. test_bugs.py 是否调整

本阶段没有删除或迁移 `test_bugs.py` 中的任何测试，保持 80 项测试兼容入口不变。

原因：

1. `test_bugs.py` 承担大量历史回归保障，贸然移除会增加覆盖丢失风险。
2. 第 79 / 80 项虽然已有独立脚本，但保留在 `test_bugs.py` 中可以维持原有“一脚本全量回归”的习惯。
3. 独立脚本作为补充入口，用于更快定位模型 UI helper 和导出 helper 问题。

## 6. pre_demo_check.py 执行流程

默认流程：

1. 使用当前解释器运行模型加载检查。
2. 运行模型 UI helper 检查。
3. 运行导出 helper 检查。
4. 运行 `test_bugs.py`。
5. 运行 `verify_optimization.py`。
6. 汇总失败项；任一失败则返回非零退出码。

带截图流程会在默认流程后先检查 `http://127.0.0.1:7860` 是否可访问，再调用 `scripts/capture_ui_screenshots.py`。

## 7. 实际执行命令

```powershell
mamba run -n yolo python -m compileall app.py src\dental_detection scripts
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python scripts\check_model_ui_helpers.py
mamba run -n yolo python scripts\check_export_helpers.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
mamba run -n yolo python scripts\pre_demo_check.py
cmd.exe /c start_project.bat
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
mamba run -n yolo python scripts\pre_demo_check.py --with-screenshots --screenshot-output docs\ai-bridge\screenshots\phase-8
git diff --check -- README.md docs\文档索引.md scripts\check_model_ui_helpers.py scripts\check_export_helpers.py scripts\pre_demo_check.py docs\ai-bridge\phase-8-test-audit.md
```

## 8. 测试结果

| 命令 | 结果 |
| --- | --- |
| `compileall` | 通过 |
| `scripts/check_model.py` | 通过 |
| `scripts/check_model_ui_helpers.py` | 通过 |
| `scripts/check_export_helpers.py` | 通过 |
| `test_bugs.py` | 通过，80 项测试完成 |
| `verify_optimization.py` | 通过 |
| `scripts/pre_demo_check.py` | 通过 |
| `git diff --check ...` | 通过，仅有 CRLF 提示 |

## 9. 服务启动结果

通过 `start_project.bat` 启动并确认服务可访问。

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`30904`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`
- 启动日志：未出现 `is not recognized` 或中文片段误执行问题。

## 10. 带截图检查结果

命令：

```powershell
mamba run -n yolo python scripts\pre_demo_check.py --with-screenshots --screenshot-output docs\ai-bridge\screenshots\phase-8
```

结果：通过。

流程中完成：

- 默认展示前检查全部通过。
- 截图前 HTTP 检查返回 `200`。
- UI 截图回归成功生成 7 张截图。

## 11. 截图路径

第八阶段截图已保存到：

`docs/ai-bridge/screenshots/phase-8/`

文件：

- `01-workbench-home.png`
- `02-workbench-model-dropdown.png`
- `03-workbench-after-example-or-upload.png`
- `04-ai-chat.png`
- `05-cases.png`
- `06-settings.png`
- `07-mobile-workbench.png`

## 12. 剩余问题

1. `test_bugs.py` 仍然较长，但本阶段为了兼容没有迁移旧测试。
2. `verify_optimization.py` 仍检查早期截图文件，后续可整理为更清晰的验证报告。
3. 截图回归依赖服务已启动，`pre_demo_check.py` 不会自动启动服务。
4. 尚未引入 pytest 或 CI，当前仍是脚本式检查体系。

## 13. 是否建议进入第九阶段

建议进入第九阶段，但继续小步推进。优先方向：

1. UI 文案常量抽离：低风险整理 `app.py` 中重复中文提示。
2. 或报告模板优化：在已有导出 smoke 和 helper 脚本基础上增强报告内容快照检查。

不建议第九阶段直接大拆 `app.py` 或迁移完整测试框架。
