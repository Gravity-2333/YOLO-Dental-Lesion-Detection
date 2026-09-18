# 第八阶段测试入口审计

更新时间：2026-07-10

## 1. 当前测试 / 检查脚本

- `test_bugs.py`：历史兼容回归入口，目前 80 项顺序测试，覆盖配置、AI 设置、历史/病例、导出、模型扫描、中文字段、CSV 注入、UI 输出顺序、模型 UI helper 和导出 helper。
- `verify_optimization.py`：综合优化验证脚本，检查 CSS、核心模块导入、测试工具、文档、旧截图和模型文件。
- `scripts/check_model.py`：展示前模型加载检查，验证默认模型权重可由当前环境加载，并输出 ultralytics 来源、task 和类别。
- `scripts/capture_ui_screenshots.py`：正式 UI 截图回归脚本，要求 Gradio 服务已启动，覆盖工作台、模型下拉、检测结果、AI 问答、病例、设置页和移动端工作台。
- `docs/ai-bridge/runtime-logs/*.py`：早期阶段取证和环境检查脚本，主要用于历史审计，不建议作为日常主入口。
- `screenshot_ui.py`、`screenshot_ai_chat.py`、`screenshot_issues.py`、`outputs/capture_full_ui.py`：早期截图脚本，已不是首选入口。
- `verify_all_fixes.py`、`check_alignment.py` 等未纳入当前主验证链路，保留为历史或临时验证工具。

## 2. 每个脚本覆盖范围

| 脚本 | 覆盖内容 | 是否作为展示前主入口 |
| --- | --- | --- |
| `scripts/check_model.py` | 默认模型加载、类别、ultralytics 来源 | 是 |
| `test_bugs.py` | 大量历史回归与核心兼容行为 | 是 |
| `verify_optimization.py` | CSS、模块、文档、截图和模型文件粗检查 | 是 |
| `scripts/capture_ui_screenshots.py` | 真实 Gradio 页面截图回归 | 可选，需服务运行 |
| `docs/ai-bridge/runtime-logs/*.py` | 阶段取证 | 否 |
| 早期截图脚本 | 历史截图入口 | 否 |

## 3. test_bugs.py 中可安全拆出的测试

以下测试与新抽离 helper 模块强相关，适合独立成轻量脚本：

- 第 79 项：模型 UI helper 输出关键展示状态，可独立检查 `src/dental_detection/model_ui.py`。
- 第 80 项：导出 helper 文件组织和安全写入，可独立检查 `src/dental_detection/exporters.py`。

本阶段新增独立脚本作为补充入口，但不从 `test_bugs.py` 删除对应测试，以保持兼容入口和历史测试覆盖稳定。

## 4. 暂时不应拆出的测试

以下测试暂时保留在 `test_bugs.py`：

- Gradio 主流程输出顺序相关测试。
- 单图 / 批量导出端到端兼容测试。
- 历史记录、病例记录、中文字段和异常 summary 兼容测试。
- AI 设置、对话失败和默认建议兼容测试。
- 与 `app.py` 私有函数、状态同步和历史路径同步强耦合的测试。

这些测试拆分需要先建立更清晰的测试模块边界，否则容易丢失历史上下文。

## 5. 重复检查

- 模型 UI helper 和导出 helper 现在会同时出现在 `test_bugs.py` 和独立脚本中，这是刻意保守处理：`test_bugs.py` 保持历史兼容入口，独立脚本用于快速定位新模块问题。
- `verify_optimization.py` 与 `check_model.py` 都会触及模型文件存在性，但 `check_model.py` 会真实加载默认模型，仍不可替代。
- 截图脚本与 `verify_optimization.py` 的旧截图检查有重叠，但前者生成新截图，后者只做旧截图存在性检查。

## 6. 答辩前最小检查链路

默认展示前建议运行：

```powershell
python scripts/pre_demo_check.py
```

该入口会执行：

- `python scripts/check_model.py`
- `python scripts/check_model_ui_helpers.py`
- `python scripts/check_export_helpers.py`
- `python test_bugs.py`
- `python verify_optimization.py`

如果需要截图回归，先启动服务，再运行：

```powershell
python scripts/pre_demo_check.py --with-screenshots --screenshot-output docs/ai-bridge/screenshots/pre-demo
```

## 7. 风险点

1. `test_bugs.py` 仍是长顺序脚本，失败定位比标准测试框架慢。
2. 展示前一键检查默认耗时较长，但覆盖更稳；可用 `--skip-slow` 跳过慢检查。
3. 截图回归依赖服务已启动，也依赖本机 Chrome / Edge 或 Playwright 浏览器 fallback。
4. 当前不引入 pytest，短期更稳，但长期测试分组和并行能力有限。
