# 第七阶段导出逻辑抽离审计

更新时间：2026-07-09

## 1. 当前 app.py 中的导出函数和代码块

本轮只审计导出相关文件组织逻辑，不改推理、AI 问答、病例保存主流程和 Gradio 输出顺序。

当前 `app.py` 中与导出相关的主要代码包括：

- `_safe_stem()`：生成报告、图片、病例等文件安全 stem。
- `_write_text()`：以临时文件替换方式写入文本。
- `_unique_report_paths()`：生成单图 ZIP 报告目录和 zip 路径。
- `_unique_batch_export_paths()`：生成批量 ZIP 报告目录和 zip 路径。
- `_unique_case_path()`：生成病例 JSON 文件路径。
- `export_batch_results()`：批量 ZIP 导出，包含图片保存、建议文本、CSV、JSON、HTML、总览文件、ZIP 打包和临时目录清理。
- `export_single_report()`：单图 ZIP 导出，包含图片保存、CSV、JSON、summary、HTML、ZIP 打包和临时目录清理。
- `export_batch_word_report()` / `export_word_report()`：Word 报告目录组织和调用 `reporting.py`。
- `save_case_record()`：病例 JSON 写入。
- `export_chat()`、`export_selected_case_record()`：对话和病例导出入口。

其中 Word 正文生成已经位于 `src/dental_detection/reporting.py`，本阶段不重复拆分正文模板。

## 2. 可以安全抽离的纯文件组织逻辑

以下逻辑不依赖 Gradio，可安全抽离：

- 安全文件名 stem 生成。
- 导出目录创建。
- 唯一导出目录生成。
- ZIP 路径生成。
- 文本、HTML、JSON、CSV 写入。
- CSV 公式注入防护写入。
- ZIP manifest 构建。
- ZIP 中添加现有文件，缺失文件安全跳过。
- 从 payload 目录创建 ZIP。
- payload 临时目录清理和空导出目录清理。

这些逻辑适合放入新增 `src/dental_detection/exporters.py`，避免让 `reporting.py` 同时承担 Word 正文生成和 ZIP 文件组织两类职责。

## 3. 暂时不应抽离的强耦合逻辑

以下逻辑本阶段保留在 `app.py`：

- `export_batch_results()` 和 `export_single_report()` 的整体函数入口：直接返回 Gradio 文件组件、路径文本和状态对象，输出顺序敏感。
- `_sync_report_path()` 与历史记录路径同步：和当前 UI 状态、历史更新调用顺序耦合。
- 批量和单图 JSON payload 的业务字段组装：涉及模型结果兼容、中文字段、检测框清洗和报告字段语义。
- HTML 报告正文模板：本阶段只移动写入动作，不改正文内容，避免截图和导出内容回归。
- Word 报告正文生成：已有 `reporting.py` 承接，不在本阶段重复拆分。

## 4. reporting.py 是否适合承接

`src/dental_detection/reporting.py` 当前主要负责 Word 报告内容生成，包括单图和批量 docx 模板、检测表、图片插入和图例说明。

ZIP、CSV、JSON、HTML 文件组织与 Word 正文生成职责不同，因此本阶段选择新增 `src/dental_detection/exporters.py`。这样可以保持 `reporting.py` 的报告正文职责清晰。

## 5. 建议新增或修改文件

- 新增 `src/dental_detection/exporters.py`
- 修改 `app.py`
- 修改 `test_bugs.py`
- 更新 `docs/文档索引.md`
- 生成 `docs/ai-bridge/phase-7-export-refactor-report.md`

## 6. 风险点

1. 导出按钮输出数量和顺序不能变化。
2. ZIP 内文件名、CSV 字段、JSON 字段和 HTML 正文不能改变。
3. CSV 公式注入防护不能回退。
4. 单图导出和批量导出的临时 payload 目录必须继续清理。
5. 缺失图片仍应按原逻辑在报告入口给出明确错误；只有 ZIP manifest 添加缺失文件的底层 helper 可以安全跳过。
6. `app.py` 已有大量历史兼容测试，抽离时要避免改变中文字段、单对象模型结果和异常 summary 的导出表现。
