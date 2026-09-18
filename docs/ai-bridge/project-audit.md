# YOLO 牙齿病变识别项目第一阶段审计报告

更新时间：2026-07-08

## 审计范围

本轮按照 `E:\code\AI\YOLO\.ai-bridge\current-plan.md` 执行，只做阅读与架构审计，不修改核心代码。

已审阅范围：

- `README.md`
- `requirements.txt`
- `start_project.bat`
- `stop_project.bat`
- `scripts/project_config.bat`
- `scripts/run_gradio_server.bat`
- `scripts/stop_project.ps1`
- `scripts/check_model.py`
- `app.py`
- `src/dental_detection/`
- `assets/workbench.css`
- `assets/workbench.js`
- `assets/examples/`
- `data/*.yaml`
- `docs/` 主要索引、进度、数据集审计和优化原则文档
- `models/` 目录结构、默认候选模型配置
- `test_bugs.py`、截图脚本和验证脚本结构

本轮未启动服务、未运行测试、未执行模型推理。真实页面视觉问题仍需后续截图验证。

## 当前架构评价

项目当前是一个“基于已训练 YOLO 模型的本地前台识别系统”，而不是训练平台。这个定位是正确的。用户主要流程是启动 Gradio 工作台，上传单张或多张牙科影像，选择模型和推理参数，查看原图、模型输入、检测结果、检测表、质量提示和辅助建议，并按需导出报告或保存病例。

整体架构已经从早期单脚本向模块化演进：

- `src/dental_detection/inference.py` 承担模型加载、预处理、推理和检测框绘制。
- `assistant.py` 承担 AI 设置、API Key 处理、OpenAI-compatible 调用、默认建议和本地记录目录。
- `reporting.py`、`case_store.py`、`history_store.py`、`batch_summary.py` 承担报告、病例、历史和批量统计。
- `model_files.py`、`model_info.py` 承担模型扫描与模型说明。
- `visualization.py` 承担结果图保存、标签绘制、局部裁剪。
- `result_levels.py`、`result_items.py`、`text_utils.py` 承担兼容层和数据清洗。

主要问题是 `app.py` 仍然过大，约三千多行，承担了 UI 组件定义、事件绑定、状态组织、模型选择、推理编排、导出 ZIP、保存病例、AI 问答、设置保存等多种职责。它已经不是简单入口，而是事实上的应用协调器和大量业务逻辑容器。后续继续加功能时，如果不进一步拆分，维护成本会明显上升。

## 优点

1. 功能闭环完整  
   单图检测、批量检测、模型切换、对比模型、CLAHE、图像质量提示、类别图例、局部裁剪、报告导出、病例记录、历史记录和 AI 问答都已有实现。

2. 项目定位清晰  
   文档明确当前系统不做训练平台、不做标注平台、不做主动学习、不做医院级系统集成，这能避免需求发散。

3. 模型工程化基础较好  
   `MODEL_REGISTRY` 明确登记两个候选模型，支持主模型和对比模型，支持模型目录扫描，并对 `.pt`、`.onnx`、`.engine`、`.mlmodel`、`.mlpackage`、`.torchscript` 做格式过滤。

4. 结果解释更贴近医疗辅助软件  
   检测类别有中文映射，置信度有关注等级和解释，报告、AI 建议和页面文案保留“不能替代专业牙科医生诊断”的安全边界。

5. 本地隐私边界较好  
   AI 模块默认只发送检测结果文本，不上传牙片图片。病例记录默认保存摘要、检测框和建议，不保存原始牙片。

6. 兼容性修复积累充分  
   `test_bugs.py` 已覆盖大量边界情况，包括异常 summary、中文字段、单对象检测框、CSV 公式注入、模型结果结构兼容等。

7. 启动脚本职责明确  
   `project_config.bat` 集中配置端口、mamba 环境、Python 路径和 Ultralytics 配置目录；`start_project.bat` 会先停止同端口旧进程再启动。

## 问题列表

### P0 问题

1. `app.py` 仍然过大且职责混杂  
   风险：后续继续加功能容易造成输出顺序错位、状态同步遗漏和回归问题。`test_bugs.py` 中已有“主流程输出组件顺序”类测试，说明这里已经是高风险区。

2. 默认模型依赖外部相邻仓库源码  
   `YOLOv8m C2f-Faster-lite` 依赖 `../yolov8-train` 的自定义 ultralytics 代码。若展示环境只复制当前项目，模型可能加载失败。当前 README 有说明，但工程层面仍缺少更显眼的启动前检查和错误引导。

3. 推理失败对用户核心流程影响极大  
   `_detect_model_path` 会把异常转为友好错误，但前端显示可能仍然是多个组件“错误”状态。核心检测链路需要稳定的端到端 smoke 测试和展示前检查清单。

4. UI 输出状态依赖长元组顺序  
   `run_single_detection`、`run_batch_detection`、`select_batch_item`、`clear_outputs` 等返回大量位置敏感输出。任何组件增删都可能把按钮文字、文件组件、路径框或状态写错位置。

### P1 问题

1. `assistant.py` 也承担过多职责  
   该模块同时包含设置、目录迁移、AI 请求、默认建议、对话保存和安全提示。建议拆分为 `settings_store.py`、`ai_client.py`、`advice.py`。

2. 导出逻辑仍有部分在 `app.py`  
   ZIP 导出、HTML 写入、CSV 写入、图片保存路径组织仍在 `app.py`。建议迁入 `reporting.py` 或新增 `exporters.py`。

3. 模型路径状态对展示场景不够显式  
   模型卡片能显示可用/缺失，但启动时缺失依赖、自定义模块缺失、GPU 不可用、权重损坏等场景需要更集中的“展示前自检”。

4. 测试脚本不是标准测试框架结构  
   `test_bugs.py` 是顺序脚本，覆盖多但粒度不利于定位。建议逐步迁移到 `pytest` 风格，不必一次性改完。

5. UI 真实布局需要截图验证  
   CSS 已包含大量对齐、下拉框、按钮、响应式规则，但真实 Gradio DOM 可能随版本变化。涉及视觉判断时应启动服务截图，而不是只读 CSS 推断。

6. 数据与模型材料边界仍需文档化  
   README 说明真实牙科图片和标签默认不提交，但 `models/` 内有权重，`transfer/` 下有训练资料压缩包，展示/提交/打包时需要清晰排除规则。

### P2 问题

1. 前端仍偏 Gradio 默认控件拼装  
   目前 CSS 已做大量修饰，但复杂工作台在 Gradio 内会受控件 DOM 变化影响。后续可考虑更明确的组件区域命名和截图基线。

2. 报告模板仍可继续专业化  
   Word/HTML 报告已有基础内容，但可继续增强模型信息、阈值说明、类别图例、检测限制、页面排版和页眉页脚。

3. 日志体系较轻  
   当前更多依赖控制台输出和友好错误消息。后续可考虑本地滚动日志，但要避免高频 TRACE 写盘。

4. 依赖版本约束偏宽  
   `requirements.txt` 使用最低版本约束。Gradio、Ultralytics、Torch 大版本变化可能影响 UI DOM、模型加载或推理行为。

## P0/P1/P2 优化优先级

### P0：核心稳定性

1. 为展示前核心流程建立检查清单：模型文件存在、自定义 ultralytics 可导入、默认模型可加载、CPU/GPU 可用、示例图可推理。
2. 把 `app.py` 中的位置敏感输出组封装成命名结构或小型 builder，降低输出错位风险。
3. 把单图/批量推理状态组织提取到独立模块，保留 UI 层只做输入输出绑定。
4. 增加“默认 baseline 展示模式”的显式说明和设置入口，避免用户展示时误选优化模型。

### P1：维护性和体验

1. 把 ZIP/HTML/CSV 导出逻辑从 `app.py` 迁入 `reporting.py` 或 `exporters.py`。
2. 拆分 `assistant.py` 中的设置存储、AI 客户端、默认建议和对话保存。
3. 将 `test_bugs.py` 分组迁移为可独立运行的测试模块。
4. 建立 UI 截图审计流程，至少覆盖工作台、设置页、AI 问答页、病例记录页。
5. 增加模型依赖缺失时的专门提示，尤其是 C2f-Faster-lite 自定义模块。

### P2：增强项

1. 美化 Word 报告模板，加入更正式的封面、模型说明和阈值解释。
2. 增加展示模式配置，例如“只用 baseline”“只用优化模型”“对比模式”。
3. 增强本地日志和导出审计记录，但控制写盘频率。
4. 为 README 增加“演示操作步骤”和“baseline 模型选择路径”。

## 后端优化建议

1. 建立应用服务层  
   新增 `src/dental_detection/workflows.py` 或 `services.py`，承接单图检测、批量检测、结果状态构建、建议生成、历史写入等流程。`app.py` 只负责 Gradio 组件和事件绑定。

2. 建立导出层  
   新增 `src/dental_detection/exporters.py`，把 `export_single_report`、`export_batch_results` 中的 ZIP、HTML、CSV、JSON 文件组织迁出。

3. 统一错误对象  
   目前已有 `friendly_error_message`，可以进一步让核心层抛出结构化错误，例如 `UserFacingError(context, reason, suggestion)`，UI 层统一转 `gr.Error`。

4. 减少状态字典的松散字段  
   当前 batch item、result、summary 都是自由 dict。建议逐步引入 dataclass 或 TypedDict，至少先为核心字段建立类型说明。

5. 限制 `app.py` 新增代码  
   后续新增功能默认进入 `src/dental_detection/` 模块，只在 `app.py` 做最薄事件绑定。

## AI 模块优化建议

1. 明确 baseline 与优化模型的工程依赖  
   `YOLOv8m 原始结构` 更适合演示稳定性，`C2f-Faster-lite` 需要自定义模块支持。建议在设置页和 README 中明确两者区别。

2. 增加模型自检函数  
   自检应验证：路径存在、后缀支持、权重可加载、类别映射为三类、是否需要自定义 ultralytics、当前环境是否满足。

3. 缓存策略可配置  
   `get_detector` 使用 `lru_cache(maxsize=2)`，适合当前两模型对比。若后续允许更多模型，需要说明缓存淘汰行为或提供清理入口。

4. 推理参数记录更显式  
   当前 summary 记录 conf、iou、imgsz、CLAHE、设备。建议报告中也固定展示这些参数，方便复现实验展示。

5. AI 建议继续保持文本边界  
   不应上传牙片给外部大模型。可以增强 prompt 中对“非诊断、非处方、复查建议”的约束。

## 前端优化建议

1. 先截图再判断视觉问题  
   需要启动服务并保存以下截图：
   - `outputs/audit_workbench.png`
   - `outputs/audit_settings_models.png`
   - `outputs/audit_ai_chat.png`
   - `outputs/audit_cases.png`

2. 控制工作台信息密度  
   当前功能很多，工作台左侧设置、右侧结果、下方导出都集中在一页。建议保持“上传-分析-查看-导出”的主路径醒目，弱化高级设置。

3. 强化展示模式  
   用户演示时需要快速切到 baseline。可以在模型卡片上明确“baseline 展示推荐”或新增演示模式提示。

4. 对 Gradio DOM 变化保持谨慎  
   CSS 中大量选择器依赖 Gradio 结构。后续升级 Gradio 后必须做截图回归。

5. 医疗软件专业感  
   当前文案安全边界较好。视觉上应继续保持克制、清晰、可读，不建议加入营销式大 hero 或装饰性背景。

## 工程规范、目录结构与测试建议

1. 文档命名已经逐步中文化，符合当前项目习惯。
2. `docs/文档索引.md` 已承担文档入口作用，后续新增审计和协作文件建议也在索引中登记。
3. 测试覆盖丰富，但建议拆分为：
   - `tests/test_inference.py`
   - `tests/test_exports.py`
   - `tests/test_cases.py`
   - `tests/test_history.py`
   - `tests/test_ui_contract.py`
   - `tests/test_ai_settings.py`
4. 截图脚本可以保留，但建议输出文件名固定并写入验证说明。
5. 启动脚本已较实用，但应避免脚本注释或路径中出现导致 CMD 误执行的异常字符。

## 重构路线图

### 第一阶段：稳定现状

- 不改功能，只增加审计文档和协作文件。
- 对核心流程做展示前自检。
- 运行现有测试和一次真实推理 smoke test。
- 启动服务并保存 UI 截图证据。

### 第二阶段：低风险拆分

- 提取单图/批量流程构建逻辑。
- 提取 ZIP/HTML/CSV 导出逻辑。
- 提取 AI 设置和 AI 客户端。
- 给主要状态 dict 增加 TypedDict 或 dataclass。

### 第三阶段：体验增强

- 增加 baseline 展示模式说明。
- 优化设置页模型卡片和模型依赖提示。
- 优化 Word 报告模板。
- 增加 UI 截图回归流程。

### 第四阶段：测试体系整理

- 将 `test_bugs.py` 分模块迁移到 `tests/`。
- 保留老脚本作为兼容入口，或改成调用 pytest。
- 建立展示前检查命令。

## 修改文件预测

后续如果按上述路线执行，可能涉及：

- `app.py`
- `README.md`
- `assets/workbench.css`
- `src/dental_detection/inference.py`
- `src/dental_detection/reporting.py`
- `src/dental_detection/assistant.py`
- `src/dental_detection/model_info.py`
- `src/dental_detection/model_files.py`
- 新增 `src/dental_detection/workflows.py`
- 新增 `src/dental_detection/exporters.py`
- 新增 `src/dental_detection/settings_store.py`
- 新增 `src/dental_detection/ai_client.py`
- 新增 `tests/`
- `docs/文档索引.md`
- `docs/ai-bridge/*`

## 风险说明

1. 核心推理链路风险  
   模型权重、Ultralytics 版本、自定义模块路径、CUDA 环境任一变化都可能导致推理失败。

2. UI 回归风险  
   Gradio 版本变化可能改变 DOM，导致按钮对齐、下拉框、路径框和响应式布局失效。

3. 状态同步风险  
   `app.py` 返回大量位置敏感元组，新增组件时容易发生输出错位。

4. 文件导出风险  
   报告导出涉及图片、CSV、JSON、HTML、Word 和 zip，需继续防止路径错误、CSV 注入、缺图崩溃和旧状态污染。

5. 医疗表达风险  
   所有页面、报告和 AI 回复必须持续保留辅助参考边界，避免诊断、处方、药物剂量、自行用药等表达。

6. 数据隐私风险  
   当前设计不上传牙片给 AI，后续不能无意改变该边界。病例记录和导出包也应默认只保存用户主动导出的内容。

## 结论

项目已经具备可展示的完整前台识别系统基础，当前最重要的不是继续堆功能，而是稳住核心检测链路、模型依赖、UI 状态流和导出流程。推荐后续采用小步、可验证、可回退的方式重构，优先降低 `app.py` 的复杂度，并为 baseline 展示建立清晰入口和自检流程。
