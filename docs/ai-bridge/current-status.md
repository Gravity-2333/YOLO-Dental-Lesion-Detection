# 当前状态

更新时间：2026-07-10

## 当前阶段

第八阶段“测试体系整理与一键展示前检查”已完成，等待第九阶段指令。

## 已完成内容

- 已按最新 `docs/ai-bridge/chatgpt-to-codex.md` 执行。
- 已参考：
  - `docs/ai-bridge/current-status.md`
  - `docs/ai-bridge/project-audit.md`
  - `docs/ai-bridge/runtime-verification.md`
  - `docs/ai-bridge/phase-3-p0-fix-report.md`
  - `docs/ai-bridge/phase-4-ui-report.md`
  - `docs/ai-bridge/phase-5-demo-model-report.md`
  - `docs/ai-bridge/phase-6-model-ui-refactor-report.md`
  - `docs/ai-bridge/phase-7-export-refactor-report.md`
- 已生成第八阶段测试入口审计：
  - `docs/ai-bridge/phase-8-test-audit.md`
- 已新增独立 helper 检查脚本：
  - `scripts/check_model_ui_helpers.py`
  - `scripts/check_export_helpers.py`
- 已新增一键展示前检查脚本：
  - `scripts/pre_demo_check.py`
- 已保留 `test_bugs.py` 80 项测试兼容入口不变。
- 已更新：
  - `README.md`
  - `docs/文档索引.md`
- 已生成第八阶段报告：
  - `docs/ai-bridge/phase-8-test-system-report.md`

## 当前运行状态

- Gradio 服务当前处于运行状态。
- 访问地址：`http://127.0.0.1:7860`
- 端口：`7860`
- Python 服务 PID：`30904`
- 服务命令行：`python app.py --server-name 127.0.0.1 --server-port 7860`
- HTTP 检查：返回 `200`

## 测试情况

| 命令 | 结果 |
| --- | --- |
| `mamba run -n yolo python -m compileall app.py src\dental_detection scripts` | 通过 |
| `mamba run -n yolo python scripts\check_model.py` | 通过 |
| `mamba run -n yolo python scripts\check_model_ui_helpers.py` | 通过 |
| `mamba run -n yolo python scripts\check_export_helpers.py` | 通过 |
| `mamba run -n yolo python test_bugs.py` | 通过，80 项测试完成 |
| `mamba run -n yolo python verify_optimization.py` | 通过 |
| `mamba run -n yolo python scripts\pre_demo_check.py` | 通过 |
| `cmd.exe /c start_project.bat` | 通过，服务成功启动 |
| `Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10` | 通过，HTTP 200 |
| `mamba run -n yolo python scripts\pre_demo_check.py --with-screenshots --screenshot-output docs\ai-bridge\screenshots\phase-8` | 通过 |
| `git diff --check ...` | 通过，仅有 CRLF 提示 |

## 展示前检查情况

一键展示前检查脚本已可用：

```powershell
python scripts/pre_demo_check.py
```

带截图检查也已验证通过：

```powershell
python scripts/pre_demo_check.py --with-screenshots --screenshot-output docs/ai-bridge/screenshots/phase-8
```

`--with-screenshots` 会先确认 `http://127.0.0.1:7860` 返回 200，再调用截图脚本。

## 截图情况

第八阶段截图目录：

`docs/ai-bridge/screenshots/phase-8/`

已生成：

- `01-workbench-home.png`
- `02-workbench-model-dropdown.png`
- `03-workbench-after-example-or-upload.png`
- `04-ai-chat.png`
- `05-cases.png`
- `06-settings.png`
- `07-mobile-workbench.png`

## 已知问题

1. `test_bugs.py` 仍然较长，本阶段为了低风险兼容没有迁移旧测试。
2. `verify_optimization.py` 仍是早期综合检查脚本，后续可继续整理为更聚焦的验证入口。
3. 截图回归需要服务已启动，`pre_demo_check.py` 不会自动启动服务。
4. 当前仍是脚本式测试体系，暂未引入 pytest 或 CI。

## 下一步建议

建议进入第九阶段，但继续小步可回退：

1. 优先做 UI 文案常量抽离，减少 `app.py` 长字符串膨胀。
2. 或做报告模板优化与内容快照检查，避免后续报告改动无验证。
3. 继续保持 `pre_demo_check.py` 作为展示前准入入口。
4. 不建议下一阶段直接大拆 `app.py` 或迁移完整测试框架。

## 后续工作规则

每次执行前优先阅读：

- `docs/ai-bridge/chatgpt-to-codex.md`
- `docs/ai-bridge/current-status.md`

不要把外部 `.ai-bridge/current-plan.md` 当作当前任务来源。

每次执行完成后只更新：

- `docs/ai-bridge/codex-to-chatgpt.md`
- `docs/ai-bridge/current-status.md`

上述文件只保留最新内容，不追加历史对话。
