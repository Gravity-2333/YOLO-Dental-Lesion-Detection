# 第七阶段导出逻辑小步抽离报告

更新时间：2026-07-09

## 1. 本阶段目标

本阶段按 `docs/ai-bridge/chatgpt-to-codex.md` 执行，只抽离导出相关的纯文件组织 helper，降低 `app.py` 中 ZIP、CSV、JSON、HTML 写入和目录管理逻辑的复杂度。

本阶段未训练模型，未修改权重，未提交 Git，未改变核心推理函数签名，未改变 Gradio 输出组件顺序，未改变导出按钮数量、报告正文和报告字段含义。

## 2. 导出逻辑审计结论

审计记录已生成：

`docs/ai-bridge/phase-7-export-audit.md`

结论是：安全文件名、导出目录创建、唯一目录生成、CSV / JSON / HTML / 文本写入、ZIP manifest 构建、ZIP 打包和临时目录清理可以安全抽离；`export_batch_results()`、`export_single_report()` 等入口仍返回 Gradio 输出并同步 `batch_state` / 历史记录，本阶段不整体外移。

## 3. 修改文件列表

- `src/dental_detection/exporters.py`
- `app.py`
- `test_bugs.py`
- `docs/文档索引.md`
- `docs/ai-bridge/phase-7-export-audit.md`
- `docs/ai-bridge/phase-7-export-refactor-report.md`
- `docs/ai-bridge/codex-to-chatgpt.md`
- `docs/ai-bridge/current-status.md`

## 4. 新增导出 helper 说明

新增 `src/dental_detection/exporters.py`，包含：

- `safe_export_stem(...)`
- `ensure_export_dir(...)`
- `unique_export_root(...)`
- `zip_path_for_root(...)`
- `write_text_file(...)`
- `write_html_file(...)`
- `write_json_file(...)`
- `write_csv_file(...)`
- `build_export_manifest(...)`
- `add_existing_file_to_zip(...)`
- `create_zip_from_manifest(...)`
- `create_zip_from_directory(...)`
- `cleanup_payload_dir(...)`
- `remove_empty_export_root(...)`

这些 helper 不依赖 Gradio，不调用模型推理，不修改报告正文内容，并继续复用 `csv_safe_row()` 和 `json_safe_value()`，保留 CSV 注入防护与中文 JSON 写入能力。

## 5. 从 app.py 抽离的逻辑

- `_safe_stem()` 改为调用 `safe_export_stem()`。
- `_write_text()` 改为调用 `write_text_file()`。
- 单图 ZIP 报告目录、批量 ZIP 报告目录、Word 报告目录改为调用 `unique_export_root()`。
- ZIP 路径改为调用 `zip_path_for_root()`。
- 批量和单图 CSV 写入改为调用 `write_csv_file()`。
- 批量和单图 JSON 写入改为调用 `write_json_file()`。
- HTML 写入改为调用 `write_html_file()`。
- ZIP 打包改为调用 `create_zip_from_directory()`。
- payload 临时目录清理和空导出目录清理改为调用 `cleanup_payload_dir()` / `remove_empty_export_root()`。

## 6. 暂未抽离的导出逻辑与原因

- `export_batch_results()` / `export_single_report()` 整体入口：返回 Gradio 文件组件、路径文本和 `batch_state`，输出顺序敏感。
- JSON payload 的业务字段组装：涉及模型结果兼容、中文字段、检测框清洗和报告字段语义。
- HTML 正文模板：本阶段只移动写入动作，不改正文内容。
- `_sync_report_path()` 和 `update_history_report_paths(...)` 调用：与 UI 状态和历史记录同步顺序耦合。
- Word 报告正文：已有 `reporting.py` 承接，本阶段不重复拆分。

## 7. 测试新增或调整情况

扩展 `test_bugs.py`，新增第 80 项测试：

- `safe_export_stem()` 处理空文件名、中文文件名、Windows 禁用字符和保留名。
- `write_csv_file()` 保留公式注入防护。
- `write_json_file()` 正确写入中文。
- `write_html_file()` 使用 UTF-8。
- `build_export_manifest()` 包含预期文件。
- `create_zip_from_manifest()` 对缺失文件安全跳过并返回 skipped 列表。

## 8. 实际执行命令

```powershell
mamba run -n yolo python -m compileall app.py src\dental_detection scripts
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
mamba run -n yolo python -c "import app; app.build_app(); print('build_app ok')"
mamba run -n yolo python - <phase7 export smoke>
cmd.exe /c start_project.bat
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
mamba run -n yolo python scripts\capture_ui_screenshots.py --output docs\ai-bridge\screenshots\phase-7
git diff --check -- app.py src\dental_detection\exporters.py test_bugs.py docs\文档索引.md docs\ai-bridge\phase-7-export-audit.md
```

## 9. 测试结果

| 命令 | 结果 |
| --- | --- |
| `compileall` | 通过 |
| `scripts/check_model.py` | 通过 |
| `test_bugs.py` | 通过，80 项测试完成 |
| `verify_optimization.py` | 通过 |
| `app.build_app()` | 通过 |
| `git diff --check ...` | 通过，仅有 CRLF 提示 |

## 10. 服务启动结果

通过 `start_project.bat` 启动并确认服务可访问。

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`24364`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`
- 启动日志：未出现 `is not recognized` 或中文片段误执行问题。

## 11. 导出功能验证结果

已通过脚本构造一条单图检测结果并触发：

- `app.export_single_report(...)`
- `app.export_batch_results(...)`

验证结果：

- 单图 ZIP 成功生成，包含 `report.html`、`detections.csv`、`detections.json`、`summary.txt`、`suggestion.txt`。
- 批量 ZIP 成功生成，包含 `detections.csv`、`detections.json`、`batch_overview.json`、`批量检测总览.html`、`summary.txt`。
- ZIP 内 JSON 可读取，模型名保持 `phase7-demo-model`。

验证输出：

```text
single_zip_ok=single_report_20260709_180436.zip; batch_zip_ok=batch_result_20260709_180436.zip
```

## 12. 截图路径

第七阶段截图已保存到：

`docs/ai-bridge/screenshots/phase-7/`

文件：

- `01-workbench-home.png`
- `02-workbench-model-dropdown.png`
- `03-workbench-after-example-or-upload.png`
- `04-ai-chat.png`
- `05-cases.png`
- `06-settings.png`
- `07-mobile-workbench.png`

## 13. 剩余问题

1. `export_batch_results()` 和 `export_single_report()` 仍在 `app.py`，因为它们返回 Gradio 输出并同步状态。
2. HTML 报告正文仍内联在 `app.py`，后续如需抽离，应先建立快照测试防止内容回归。
3. `test_bugs.py` 已继续增长到 80 项，后续可考虑按模块逐步拆分。
4. 截图回归仍需手动运行，暂未纳入 CI 或一键验证脚本。

## 14. 是否建议进入第八阶段

建议进入第八阶段，但继续小步推进。优先方向建议二选一：

1. UI 文案常量抽离：低风险整理重复中文提示，减少 `app.py` 字符串膨胀。
2. 测试体系整理：先把导出 helper 和模型 UI helper 测试迁出为独立脚本或测试模块。

不建议第八阶段直接大拆单图 / 批量检测主流程。
