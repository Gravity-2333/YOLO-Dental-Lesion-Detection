# 第二阶段运行验证与截图取证报告

更新时间：2026-07-09

## 1. 本次实际执行命令

本次只以 `docs/ai-bridge/chatgpt-to-codex.md` 为当前任务来源，并参考 `docs/ai-bridge/current-status.md` 与 `docs/ai-bridge/project-audit.md`。没有再把外部 `.ai-bridge/current-plan.md` 作为当前任务来源。

实际执行命令：

```powershell
mamba run -n yolo python docs\ai-bridge\runtime-logs\env_check.py
mamba run -n yolo python docs\ai-bridge\runtime-logs\custom_dependency_check.py
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
cmd /c start_project.bat
mamba run -n yolo python docs\ai-bridge\runtime-logs\capture_runtime_screenshots.py
```

辅助检查命令：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
Get-NetTCPConnection -LocalPort 7860
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*app.py*' }
```

运行日志保存在：

- `docs/ai-bridge/runtime-logs/01-env-check.log`
- `docs/ai-bridge/runtime-logs/02-custom-dependency-check.log`
- `docs/ai-bridge/runtime-logs/03-check-model.log`
- `docs/ai-bridge/runtime-logs/04-test-bugs.log`
- `docs/ai-bridge/runtime-logs/05-verify-optimization.log`
- `docs/ai-bridge/runtime-logs/06-start-project.log`
- `docs/ai-bridge/runtime-logs/07-screenshots-command.log`
- `docs/ai-bridge/runtime-logs/06-screenshots.log`

## 2. 环境检查结果

使用环境：

- Python 可执行文件：`D:\studysorft\MiniForge3\envs\yolo\python.exe`
- Python 版本：`3.10.20`
- 平台：`Windows-10-10.0.22631-SP0`
- 运行方式：`mamba run -n yolo python ...`

## 3. 依赖导入结果

| 依赖 | 结果 | 版本 / 说明 |
| --- | --- | --- |
| `gradio` | 通过 | `6.14.0` |
| `torch` | 通过 | `2.5.1+cu121` |
| `cv2` | 通过 | `4.13.0` |
| `PIL` | 通过 | `12.1.1` |
| `ultralytics` 直接导入 | 失败 | `ModuleNotFoundError: No module named 'ultralytics'` |
| 插入 `../yolov8-train` 后导入 `ultralytics` | 通过 | 使用 `E:\code\AI\YOLO\yolov8-train\ultralytics\__init__.py` |

说明：当前 `yolo` 环境里没有安装 site-packages 版 `ultralytics`，项目依赖同级 `../yolov8-train` 源码。应用主流程会在 `src/dental_detection/inference.py` 中插入该路径，因此 Gradio 服务可以启动；但独立脚本如果没有同样插入路径，会导入失败。

## 4. CUDA / 设备检查结果

| 项目 | 结果 |
| --- | --- |
| CUDA 是否可用 | 是 |
| GPU 数量 | 1 |
| GPU 名称 | `NVIDIA GeForce RTX 4060 Laptop GPU` |
| PyTorch CUDA 版本 | `12.1` |
| Torch 版本 | `2.5.1+cu121` |

## 5. 模型文件检查结果

| 模型 | 路径 | 是否存在 | 大小 |
| --- | --- | --- | ---: |
| baseline / YOLOv8m 原始结构 | `models/final_candidates/yolov8m_1280_full/weights/best.pt` | 是 | 49.69 MB |
| YOLOv8m C2f-Faster-lite | `models/final_candidates/yolov8m_c2f_faster_lite_1280_full/weights/best.pt` | 是 | 39.86 MB |

当前界面截图中，设置页模型卡片显示 baseline `YOLOv8m 原始结构` 被选中；C2f-Faster-lite 也显示为可用。

## 6. C2f-Faster-lite 外部依赖检查结果

| 检查项 | 结果 |
| --- | --- |
| `../yolov8-train` 是否存在 | 是 |
| `from ultralytics.nn.modules import C2fFasterLite` | 通过 |
| `from ultralytics.nn.modules.dental_neck import FasterLiteBottleneck, C2fFasterLite` | 通过 |
| 加载 C2f-Faster-lite 权重 | 通过 |
| 读取类别 | `{0: 'Caries', 1: 'Periapical_Lesion', 2: 'Impacted'}` |

补充说明：从 `ultralytics.nn.modules.block` 直接导入 `C2fFasterLite` 会失败，因为当前实现位置在 `ultralytics.nn.modules.dental_neck`，并由 `ultralytics.nn.modules` 导出。应用加载模型时使用的路径是可行的。

## 7. 测试脚本运行结果

| 命令 | 结果 | 关键结论 |
| --- | --- | --- |
| `mamba run -n yolo python scripts\check_model.py` | 失败 | 脚本开头直接 `from ultralytics import YOLO`，但当前环境未安装 site-packages 版 `ultralytics`，因此报 `ModuleNotFoundError`。 |
| `mamba run -n yolo python test_bugs.py` | 通过 | 78 项测试全部通过，覆盖历史、病例、导出、UI 输出顺序、中文字段、CSV 转义等。 |
| `mamba run -n yolo python verify_optimization.py` | 通过 | CSS、核心模块、测试工具、文档、旧截图和模型文件检查均通过。 |

真实问题：`scripts/check_model.py` 与应用主流程的 ultralytics 路径处理不一致。应用可以启动，但独立模型检查脚本失败。这会影响展示前自检和 README 中的“检查模型”命令。

## 8. Gradio 服务启动结果

实际启动命令：

```powershell
cmd /c start_project.bat
```

启动结果：

- 服务启动成功。
- 访问地址：`http://127.0.0.1:7860`
- HTTP 检查结果：`200`
- 监听端口：`7860`
- Python 服务进程 PID：`26560`
- 进程命令行：`python app.py --server-name 127.0.0.1 --server-port 7860`

启动日志中发现一条真实问题：

```text
'��行日志和可能的报错；关闭该窗口也会停止前端服务。' is not recognized as an internal or external command,
operable program or batch file.
```

该问题没有阻断服务启动，但说明 `start_project.bat` 中某条中文提示在当前终端编码/管道环境下被截断并被 CMD 当成命令执行。此前用户也遇到过类似 `'""""' is not recognized` 一类启动脚本显示问题，因此建议作为 P0/P1 之间的启动体验问题修复。

另一个观察：通过自动化终端执行 `cmd /c start_project.bat` 时，命令会因新开的 `cmd /k` 后端窗口保持管道而没有在 30 秒内正常返回，工具侧记录为超时；但服务实际已经启动并可访问。对普通双击/手动启动影响可能较小，但自动化验证和报告记录会受影响。

## 9. 截图清单

截图保存目录：

`docs/ai-bridge/screenshots/`

| 文件 | 说明 | 结果 |
| --- | --- | --- |
| `01-workbench-home.png` | 检测工作台首屏 | 已生成 |
| `02-workbench-model-dropdown.png` | 设置页模型选择下拉框打开状态 | 已生成 |
| `03-workbench-after-example-or-upload.png` | 上传合成示例图并完成检测后的工作台 | 已生成 |
| `04-ai-chat.png` | AI 问答页 | 已生成 |
| `05-cases.png` | 病例记录页 | 已生成 |
| `06-settings.png` | 设置页 | 已生成 |
| `07-mobile-workbench.png` | 移动端宽度检测工作台 | 已生成 |

截图取证使用系统 Chrome：

`C:\Program Files\Google\Chrome\Application\chrome.exe`

原因：当前 Playwright 包存在，但内置 Chromium 浏览器未安装；直接 `p.chromium.launch()` 会提示缺少 `chromium_headless_shell`。改用本机 Chrome 后截图成功。

## 10. 发现的真实问题

### P0

1. `scripts/check_model.py` 无法运行  
   该脚本没有像应用主流程一样插入 `../yolov8-train`，导致 `from ultralytics import YOLO` 直接失败。影响 README 中模型检查命令和展示前自检。

2. 启动脚本存在编码/管道环境下的异常提示  
   `start_project.bat` 服务能启动，但日志中出现中文片段被当作命令执行的问题。它不阻塞当前服务启动，但会给用户造成“启动失败”的错觉。

### P1

1. 项目依赖 `../yolov8-train` 源码，但依赖关系没有通过统一自检入口显式说明  
   当前应用能跑，脚本会失败，说明依赖注入点分散。建议增加统一的依赖检查工具。

2. `start_project.bat` 使用新窗口 `cmd /k`，自动化验证不容易稳定捕获后端日志  
   对截图取证和 CI 式验证不友好。建议保留用户双击脚本，同时提供一个可阻塞、可重定向日志的验证启动脚本。

3. 模型下拉框长路径可读但信息密度较高  
   截图中长模型路径会换行，占用较大空间。箭头没有被遮挡，属于可用但仍可优化的体验问题。

### P2

1. 移动端页面可访问，但首屏信息较长  
   移动端导航使用“更多”折叠菜单，步骤卡片正常换行；主要功能可见，但上传区需要滚动查看更多。

2. 截图脚本依赖本机 Chrome  
   若换机器执行，需要确保 Chrome 或 Playwright 浏览器可用。

## 11. 后续建议的 P0 / P1 / P2 修改顺序

### P0

1. 修复 `scripts/check_model.py`，使其与应用主流程一致，优先插入 `PROJECT_ROOT` 和 `../yolov8-train` 后再导入 `ultralytics`。
2. 修复 `start_project.bat` 中文提示在 CMD/管道环境下被误执行的问题。
3. 增加一个展示前自检命令，覆盖 Python、关键依赖、模型文件、C2f 自定义模块、默认模型加载和服务端口。

### P1

1. 增加自动化友好的启动方式，例如 `scripts/run_gradio_server.bat` 配合明确日志输出，或新增 `scripts/start_for_verification.ps1`。
2. 在设置页和 README 中更明确地区分 baseline 与 C2f-Faster-lite，并说明 C2f 对 `../yolov8-train` 的依赖。
3. 优化模型下拉框显示，减少长路径对阅读的干扰，例如保留名称为主、路径放到说明或反馈中。

### P2

1. 建立固定截图回归脚本，输出到 `docs/ai-bridge/screenshots/` 或 `outputs/ui-regression/`。
2. 优化移动端首屏密度。
3. 将 `test_bugs.py` 逐步拆分为标准测试目录。

## 12. 是否可以进入代码优化阶段

可以进入第三阶段代码优化，但建议第一批优化只处理 P0 级低风险修复：

- 修复 `scripts/check_model.py` 的导入路径。
- 修复启动脚本异常提示。
- 增加或整理展示前自检入口。

不建议马上做大规模重构。当前 Gradio 服务可以启动，核心 UI 能打开，上传示例图后能生成检测结果，`test_bugs.py` 通过 78 项测试，说明可以开始有证据地做小步优化。

## 13. 如果暂缓代码优化，需要先解决什么

如果希望先把展示环境完全稳定下来，应先解决：

1. `scripts/check_model.py` 失败。
2. `start_project.bat` 日志中的乱码命令错误。
3. Playwright 内置浏览器缺失，或在截图脚本中明确使用本机 Chrome。

这些问题解决后，展示前自检链路会更顺滑。
