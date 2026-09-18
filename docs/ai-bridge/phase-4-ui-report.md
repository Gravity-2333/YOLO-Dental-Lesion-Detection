# 第四阶段 UI / 展示体验优化报告

更新时间：2026-07-09

## 1. 本阶段目标

基于现有可运行系统，做低风险 UI 和展示体验优化，让项目更适合阶段性成果汇报和答辩演示。本阶段不训练模型、不修改权重、不改变默认模型加载逻辑、不重写 Gradio 应用。

## 2. 修改文件列表

- `docs/ai-bridge/ui-audit-phase-4.md`
- `docs/ai-bridge/runtime-logs/capture_phase4_screenshots.py`
- `app.py`
- `assets/workbench.css`
- `src/dental_detection/model_info.py`

## 3. UI 审计结论

完整审计见：

`docs/ai-bridge/ui-audit-phase-4.md`

主要结论：

1. 检测工作台主路径基本清晰，但缺少“选择模型”和演示推荐提示。
2. 设置页模型卡片方向正确，但需要更清楚地区分 baseline、优化模型、当前默认、当前选中和依赖状态。
3. AI 问答页需要前置“不上传牙片，只发送检测文本摘要”的隐私边界。
4. 病例记录页需要前置本地保存和不自动保存原始牙片的说明。
5. 移动端没有明显横向溢出，但首屏垂直信息偏长，需要压缩和增强响应式约束。

## 4. 实际修改内容

### 检测工作台

- 将顶部流程从“上传影像、开始分析、查看结果、保存或导出”调整为“上传影像、选择模型、开始分析、查看并导出”。
- 增加演示提示，说明 baseline 适合稳定对照，C2f-Faster-lite 是优化模型并依赖同级 `../yolov8-train`。
- 上传区说明改为更明确的空状态引导。
- 结果区增加空状态说明，避免未检测时看起来像异常或错误。
- 推理设置说明强调常规演示保持默认参数即可，模型切换在设置页完成。

### 设置页模型展示

- 模型卡片更明确地区分：
  - baseline 模型
  - 优化模型
  - 当前默认模型
  - 当前选中模型
  - 可用 / 缺失 / 依赖缺失
- C2f-Faster-lite 卡片新增自定义依赖说明：

```text
依赖同级目录 ../yolov8-train 中的自定义 ultralytics 代码。
```

- 模型路径改为紧凑省略显示，并保留 `title` 作为完整路径提示。
- 设置页帮助说明补充迁移项目时需要保留 `../yolov8-train`，依赖缺失时建议使用 baseline。

### AI 问答页

- 增加隐私边界说明：默认只发送检测文本摘要，不上传牙片图片。
- 增加安全边界说明：AI 回复仅供辅助参考，不能替代专业牙科医生诊断。
- 增加接口配置说明，引导用户到“设置 - AI 建议”配置 Base URL、模型和 API Key。

### 病例记录页

- 增加本地保存说明：病例记录保存在本机数据目录，默认不上传云端。
- 增加不保存原片说明：只保存摘要、检测框和建议，不自动保存原始牙片图片。
- 已保存病例区域增加无记录时的操作引导。

### CSS / 移动端

- 增加工作流提示、结果区说明、隐私/安全提示、模型卡片徽标等样式。
- 模型卡片桌面端改为两列，更适合当前 baseline 与优化模型两张卡片。
- 移动端强化单列布局，压缩顶部和上传区高度，继续避免横向溢出。

## 5. 每个页面优化说明

| 页面 | 优化说明 |
| --- | --- |
| 检测工作台 | 主流程加入“选择模型”，新增演示提示和结果区空状态说明。 |
| 设置页 | 模型卡片新增 baseline、优化模型、当前默认、当前选中和依赖状态。 |
| AI 问答 | 前置隐私、安全和接口配置说明。 |
| 病例记录 | 前置本地保存和不保存原片说明，强化无记录引导。 |
| 移动端 | 流程提示、上传区和模型/提示块在窄屏下保持单列可读。 |

## 6. 移动端优化说明

移动端主要通过 CSS 完成：

- `.notice-grid` 在窄屏切换为单列。
- `.workflow-hint` 和 `.result-stage-note` 在窄屏切换为单列。
- 上传区和结果图容器降低最小高度，减少首屏被单个控件占满。
- 保留表格横向滚动，避免强行压缩导致文字重叠。

## 7. 测试命令和结果

| 命令 | 结果 |
| --- | --- |
| `mamba run -n yolo python -m compileall app.py src\dental_detection docs\ai-bridge\runtime-logs\capture_phase4_screenshots.py` | 通过 |
| `mamba run -n yolo python scripts\check_model.py` | 通过 |
| `mamba run -n yolo python test_bugs.py` | 通过，78 项测试 |
| `mamba run -n yolo python verify_optimization.py` | 通过 |
| `git diff --check -- app.py assets\workbench.css src\dental_detection\model_info.py docs\ai-bridge\ui-audit-phase-4.md docs\ai-bridge\runtime-logs\capture_phase4_screenshots.py` | 通过，仅有 CRLF 提示 |

## 8. 服务启动结果

通过 `start_project.bat` 启动并确认服务可访问。

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`53164`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`
- 启动日志：未出现 `is not recognized` 或中文片段误执行问题。

## 9. 截图路径

第四阶段截图已保存到：

`docs/ai-bridge/screenshots/phase-4/`

文件：

- `01-workbench-home-after.png`
- `02-workbench-model-dropdown-after.png`
- `03-workbench-after-example-or-upload-after.png`
- `04-ai-chat-after.png`
- `05-cases-after.png`
- `06-settings-after.png`
- `07-mobile-workbench-after.png`

## 10. 剩余 UI 问题

1. 高级模型下拉框仍会显示 `last.pt`、预训练模型和早期模型，答辩时可能误选；是否隐藏需要 ChatGPT 和用户确认。
2. 模型选择仍主要在设置页完成；是否要把主模型卡片直接放进检测工作台，需要进一步产品决策。
3. `app.py` 仍然较大，本阶段按要求只做文案和低风险 UI 修改，没有结构性拆分。
4. 截图脚本已可用，但仍属于协作取证脚本，后续可整理成正式 UI 回归工具。

## 11. 是否建议进入第五阶段代码结构优化

建议进入第五阶段，但范围应先保持小步：

1. 不直接大拆 `app.py`。
2. 优先提取 UI 文案/模型展示 helper 或导出逻辑。
3. 保留现有测试和截图回归。
4. 继续避免改变推理函数签名和输出组件顺序。
