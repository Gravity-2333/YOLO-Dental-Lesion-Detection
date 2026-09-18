# 第六阶段模型 UI helper 抽离审计

更新时间：2026-07-09

## 1. 当前散落在 app.py 的模型展示代码

本轮只审计模型展示和模型选择 UI 状态，不涉及推理、导出、AI 问答和病例流程。

当前 `app.py` 中与模型展示相关的代码主要包括：

- `_recommended_model_paths()`：从 `MODEL_REGISTRY` 生成推荐模型路径集合。
- `refresh_model_choices()`：根据“显示高级模型 / 实验权重”开关刷新下拉框，并拼接提示文案。
- `_workbench_model_status_html()`：生成检测工作台轻量模型状态块。
- `_model_card_choices()`：将模型卡片转换为 Gradio Radio choices。
- `_current_model_info_markdown()`：根据当前路径选择模型说明 markdown。
- `apply_model_card()`：应用设置页模型卡片，并刷新卡片、说明和下拉框。
- 设置页内联 HTML：模型选择标题、推荐演示流程、模型卡片 HTML。
- 检测工作台内联 HTML：当前模型状态块。

其中 HTML 展示逻辑还分布在 `src/dental_detection/model_info.py` 的 `model_cards_html()` 中。

## 2. 可以安全抽离的内容

以下内容是纯展示逻辑或轻量状态说明，适合抽离到新的 `model_ui.py`：

- 设置页模型卡片 HTML。
- 检测工作台轻量模型状态 HTML。
- 推荐演示流程 HTML。
- 高级模型风险提示 HTML。
- 长模型路径紧凑显示 HTML。

这些函数可以保持纯函数化，不直接依赖 Gradio 组件，不加载模型，不扫描文件，只消费传入的模型卡片、路径和推荐路径集合。

## 3. 暂时不应抽离的内容

以下内容本阶段暂时保留在 `app.py`：

- `refresh_model_choices()`：返回 `gr.update(...)`，直接耦合 Gradio 组件状态。
- `apply_model_card()`：涉及 Gradio 事件输出数量和输出顺序，移动风险较高。
- `_current_model_info_markdown()`：同时处理注册模型与自定义模型路径，和设置页事件绑定关系较近。
- `_recommended_model_paths()`：依赖 `MODEL_REGISTRY`，体量很小，留在 `app.py` 更直观。

## 4. 预计新增 / 修改文件

- 新增 `src/dental_detection/model_ui.py`
- 修改 `app.py`
- 修改 `src/dental_detection/model_info.py`
- 修改或扩展 `test_bugs.py`
- 更新 `docs/文档索引.md`
- 生成 `docs/ai-bridge/phase-6-model-ui-refactor-report.md`

## 5. 风险点

1. Gradio 事件输出顺序不能改变，尤其是 `apply_model_card()` 和 `apply_selected_model()` 的输出列表。
2. 模型卡片 HTML class 名称必须沿用现有 CSS，否则截图会回归。
3. 高级模型提示不应改变模型扫描结果，只改变展示和文案。
4. 工作台模型状态块只做轻量提示，不应引入模型加载或文件扫描。
5. `test_bugs.py` 是顺序脚本，新增测试应小而稳，避免引入依赖服务启动的测试。
