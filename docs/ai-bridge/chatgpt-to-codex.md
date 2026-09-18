# ChatGPT 给 Codex 的当前任务

更新时间：2026-07-09

## 当前任务来源

只以本文件为准。

外部 `.ai-bridge/current-plan.md` 只是第一阶段启动计划，不再作为当前任务来源。

执行任务前必须阅读：

* `docs/ai-bridge/current-status.md`
* `docs/ai-bridge/project-audit.md`
* `docs/ai-bridge/runtime-verification.md`
* `docs/ai-bridge/phase-3-p0-fix-report.md`
* `docs/ai-bridge/phase-4-ui-report.md`
* `docs/ai-bridge/phase-5-demo-model-report.md`
* `docs/ai-bridge/phase-6-model-ui-refactor-report.md`
* `docs/ai-bridge/phase-7-export-refactor-report.md`

执行完成后只更新：

* `docs/ai-bridge/codex-to-chatgpt.md`
* `docs/ai-bridge/current-status.md`

上述两个文件只保留最新内容，不追加历史对话。

---

# 第八阶段任务：测试体系整理与一键展示前检查

## 本阶段目标

第七阶段已经完成导出逻辑小步抽离。当前 `test_bugs.py` 已增长到 80 项，继续把所有测试堆在一个脚本里会降低定位效率。

第八阶段目标是整理测试入口，但不要大规模迁移测试框架。

重点目标：

1. 将新抽离模块的测试独立出来。
2. 保留 `test_bugs.py` 作为兼容入口。
3. 新增“一键展示前检查”脚本，用于答辩前快速确认项目能跑。
4. 不引入复杂测试框架依赖。
5. 不强制 pytest。
6. 不改变业务功能。

---

## 执行边界

* 不训练模型。
* 不提交 Git。
* 不改模型权重。
* 不大规模拆分 `app.py`。
* 不改变核心推理函数签名。
* 不改变 Gradio 输出组件顺序。
* 不改变现有 UI 行为。
* 不删除 `test_bugs.py`。
* 不强制引入 pytest。
* 本阶段只整理测试入口、检查脚本和相关文档。
* 如果某项测试迁移风险高，先保留原状并写入报告。

---

## 任务 1：审计当前测试和验证入口

阅读并审计：

```text id="4splfx"
test_bugs.py
verify_optimization.py
scripts/check_model.py
scripts/capture_ui_screenshots.py
```

同时查看是否已有其他验证脚本。

生成：

```text id="ouip64"
docs/ai-bridge/phase-8-test-audit.md
```

内容包括：

1. 当前有哪些测试 / 检查脚本。
2. 每个脚本覆盖什么。
3. `test_bugs.py` 内哪些测试可以安全拆出。
4. 哪些测试暂时不应拆出。
5. 是否存在重复检查。
6. 答辩前最小检查链路应该包含哪些命令。
7. 风险点。

---

## 任务 2：新增独立 helper 检查脚本

优先新增两个轻量脚本：

```text id="87w1h5"
scripts/check_model_ui_helpers.py
scripts/check_export_helpers.py
```

### `scripts/check_model_ui_helpers.py`

覆盖第六阶段新增的：

```text id="5txgvg"
src/dental_detection/model_ui.py
```

至少检查：

1. baseline 状态 HTML 包含“稳定对照”。
2. C2f-Faster-lite 状态 HTML 包含 `../yolov8-train`。
3. 高级模型状态 HTML 包含“不建议答辩临时使用”或等价提示。
4. 长路径显示会省略，但保留完整 `title`。
5. 推荐演示说明不为空。
6. 高级模型警告不为空。

### `scripts/check_export_helpers.py`

覆盖第七阶段新增的：

```text id="r1ayek"
src/dental_detection/exporters.py
```

至少检查：

1. `safe_export_stem` 能处理空文件名、中文、特殊字符、Windows 保留名。
2. CSV 写入保留公式注入防护。
3. JSON 写入能正确保留中文。
4. HTML 写入使用 UTF-8。
5. ZIP manifest 包含预期文件。
6. 缺失文件加入 ZIP 时安全跳过并记录 skipped。
7. 临时目录清理逻辑可正常执行。

要求：

* 两个脚本都可以直接用 `python scripts/xxx.py` 运行。
* 成功时输出清晰的 `PASS`。
* 失败时抛出明确异常或输出明确失败项。
* 不依赖网络。
* 不启动 Gradio。
* 不训练模型。
* 使用临时目录时必须自动清理。

---

## 任务 3：保留 test_bugs.py 兼容入口

不要删除 `test_bugs.py` 里的测试。

可以选择低风险方式：

### 方案 A：test_bugs.py 保留所有现有测试

新增脚本只是补充独立入口。

### 方案 B：test_bugs.py 调用新 helper 检查脚本中的函数

如果实现简单，可以复用新脚本中的检查函数，避免重复逻辑。

要求：

1. `python test_bugs.py` 仍然通过。
2. 当前 80 项测试数量可以保持 80，也可以合理增加。
3. 不要因为整理测试导致旧测试覆盖丢失。
4. 如果没有把测试从 `test_bugs.py` 移走，需要在报告说明这是为了低风险兼容。

---

## 任务 4：新增一键展示前检查脚本

新增：

```text id="nvk5uy"
scripts/pre_demo_check.py
```

目标：答辩或展示前一键运行核心检查。

默认执行：

```text id="3rbi7j"
python scripts/check_model.py
python scripts/check_model_ui_helpers.py
python scripts/check_export_helpers.py
python test_bugs.py
python verify_optimization.py
```

可选执行截图回归，例如参数：

```bash id="jvv1ax"
python scripts/pre_demo_check.py --with-screenshots --screenshot-output docs/ai-bridge/screenshots/pre-demo
```

要求：

1. 默认不启动训练。
2. 默认不修改核心业务文件。
3. 检查失败时汇总失败命令。
4. 检查成功时输出清晰摘要。
5. 支持 `--skip-slow` 或类似参数，如果某些检查耗时可跳过。
6. 支持 `--with-screenshots`，调用 `scripts/capture_ui_screenshots.py`。
7. 如果服务未启动而用户要求截图，给出明确提示。
8. 尽量使用当前 Python 解释器执行子脚本，不要硬编码 mamba。
9. 不依赖 pytest。

---

## 任务 5：文档更新

更新：

```text id="zafm0l"
README.md
docs/文档索引.md
```

README 中增加简短说明：

1. 如何运行展示前检查：

```bash id="ie7g43"
python scripts/pre_demo_check.py
```

2. 如何带截图运行：

```bash id="nmm2le"
python scripts/pre_demo_check.py --with-screenshots --screenshot-output docs/ai-bridge/screenshots/pre-demo
```

3. 如果只检查模型 UI helper：

```bash id="qj8j34"
python scripts/check_model_ui_helpers.py
```

4. 如果只检查导出 helper：

```bash id="k6bgig"
python scripts/check_export_helpers.py
```

不要让 README 变得过长。

`docs/文档索引.md` 增加第八阶段报告入口和新增脚本入口。

---

## 任务 6：验证

完成修改后运行：

```bash id="0o4jl6"
python -m compileall app.py src/dental_detection scripts
python scripts/check_model.py
python scripts/check_model_ui_helpers.py
python scripts/check_export_helpers.py
python test_bugs.py
python verify_optimization.py
python scripts/pre_demo_check.py
```

然后确认服务：

```bat id="n9g5k6"
start_project.bat
```

确认：

```text id="u5ejyt"
http://127.0.0.1:7860
```

返回 200。

再运行带截图检查：

```bash id="cx4e97"
python scripts/pre_demo_check.py --with-screenshots --screenshot-output docs/ai-bridge/screenshots/phase-8
```

截图保存到：

```text id="5evs3o"
docs/ai-bridge/screenshots/phase-8/
```

---

## 任务 7：生成第八阶段报告

生成：

```text id="2gbjd4"
docs/ai-bridge/phase-8-test-system-report.md
```

报告必须包括：

1. 本阶段目标。
2. 测试入口审计结论。
3. 修改文件列表。
4. 新增脚本说明。
5. `test_bugs.py` 是否调整，以及原因。
6. `pre_demo_check.py` 执行流程。
7. 实际执行命令。
8. 测试结果。
9. 服务启动结果。
10. 带截图检查结果。
11. 截图路径。
12. 剩余问题。
13. 是否建议进入第九阶段 UI 文案常量抽离或继续做报告模板优化。

---

## 任务 8：更新协作文件

执行完成后更新：

```text id="uessdd"
docs/ai-bridge/codex-to-chatgpt.md
docs/ai-bridge/current-status.md
```

`codex-to-chatgpt.md` 必须包括：

* 第八阶段是否完成。
* 修改了哪些文件。
* 新增了哪些测试 / 检查脚本。
* `test_bugs.py` 是否保持兼容。
* `pre_demo_check.py` 是否可用。
* 哪些验证通过。
* 哪些验证失败。
* 新截图路径。
* 需要 ChatGPT 重点查看的问题。
* 是否建议进入第九阶段。

`current-status.md` 必须包括：

* 当前阶段。
* 已完成内容。
* 当前运行状态。
* 测试情况。
* 展示前检查情况。
* 截图情况。
* 已知问题。
* 下一步建议。

---

## 完成后停止

完成第八阶段后，不要继续主动抽离 UI 文案常量，也不要大拆 `app.py`。

等待 ChatGPT 基于：

* `docs/ai-bridge/phase-8-test-audit.md`
* `docs/ai-bridge/phase-8-test-system-report.md`
* `docs/ai-bridge/screenshots/phase-8/`
* `docs/ai-bridge/codex-to-chatgpt.md`
* `docs/ai-bridge/current-status.md`

给出第九阶段指令。
