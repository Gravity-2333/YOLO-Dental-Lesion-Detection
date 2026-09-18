# 第三阶段 P0 运行可靠性修复报告

更新时间：2026-07-09

## 1. 修改目标

本阶段只处理第二阶段真实暴露的 P0 运行可靠性问题：

1. 统一 `scripts/check_model.py` 与应用主流程的 `../yolov8-train` 导入路径。
2. 修复启动脚本在 CMD 编码或重定向环境下出现中文提示误执行的问题。
3. 为截图脚本增加 Playwright Chromium 缺失时的系统 Chrome / Edge fallback。

本阶段未训练模型，未修改权重，未改变默认模型选择逻辑，未做 UI 重设计。

## 2. 修改文件列表

- `src/dental_detection/runtime_paths.py`
- `src/dental_detection/browser_fallback.py`
- `src/dental_detection/config.py`
- `src/dental_detection/inference.py`
- `scripts/check_model.py`
- `start_project.bat`
- `stop_project.bat`
- `scripts/stop_project.ps1`
- `screenshot_ui.py`
- `screenshot_ai_chat.py`
- `screenshot_issues.py`
- `outputs/capture_full_ui.py`

## 3. 修复方式

### 3.1 ultralytics 路径初始化不一致

新增 `src/dental_detection/runtime_paths.py`，集中提供：

```python
ensure_project_ultralytics_path() -> Path | None
```

该函数从项目根目录推导同级 `../yolov8-train`，确认其中存在 `ultralytics/` 后再插入 `sys.path`，并避免重复插入。

`scripts/check_model.py` 现在会在导入 `ultralytics` 前先插入项目根目录并调用该函数；`src/dental_detection/inference.py` 也改为复用该函数，避免继续维护重复的路径插入逻辑。

### 3.2 启动脚本日志误执行

`start_project.bat` 中容易受编码和 CMD 解析影响的中文提示已改为简单 ASCII 提示，并将新窗口启动命令改为：

```bat
start "YOLO Dental Gradio" "%ComSpec%" /k ""%PROJECT_ROOT%scripts\run_gradio_server.bat""
```

同时将 `stop_project.bat` 和 `scripts/stop_project.ps1` 的输出改为 ASCII，并让 `--from-start` 静默关闭旧服务时不再输出关闭 PID，避免启动日志里继续出现乱码片段。

### 3.3 截图脚本浏览器 fallback

新增 `src/dental_detection/browser_fallback.py`，优先尝试 Playwright 默认 Chromium；如果本机未安装 Playwright Chromium，则依次尝试：

- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
- `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

如果仍不可用，会提示运行：

```bash
python -m playwright install chromium
```

已接入 `screenshot_ui.py`、`screenshot_ai_chat.py`、`screenshot_issues.py` 和 `outputs/capture_full_ui.py`。

## 4. 实际执行命令

```powershell
mamba run -n yolo python scripts\check_model.py
mamba run -n yolo python -m compileall src\dental_detection scripts\check_model.py screenshot_ui.py screenshot_ai_chat.py screenshot_issues.py outputs\capture_full_ui.py
mamba run -n yolo python test_bugs.py
mamba run -n yolo python verify_optimization.py
cmd.exe /c start_project.bat
Invoke-WebRequest -Uri http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 10
mamba run -n yolo python screenshot_ui.py
mamba run -n yolo python docs\ai-bridge\runtime-logs\capture_runtime_screenshots.py
git diff --check -- start_project.bat stop_project.bat scripts\stop_project.ps1 scripts\check_model.py src\dental_detection\config.py src\dental_detection\inference.py src\dental_detection\runtime_paths.py src\dental_detection\browser_fallback.py screenshot_ui.py screenshot_ai_chat.py screenshot_issues.py outputs\capture_full_ui.py
```

## 5. 验证结果

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `mamba run -n yolo python scripts\check_model.py` | 通过 | 成功加载默认 C2f-Faster-lite 权重，`ultralytics_source` 为 `E:\code\AI\YOLO\yolov8-train`。 |
| `mamba run -n yolo python -m compileall ...` | 通过 | 新增和修改的 Python 文件语法正常。 |
| `mamba run -n yolo python test_bugs.py` | 通过 | 78 项测试全部通过。 |
| `mamba run -n yolo python verify_optimization.py` | 通过 | CSS、核心模块、测试工具、文档、截图和模型文件检查均通过。 |
| `cmd.exe /c start_project.bat` | 通过 | 启动包装脚本正常返回，Gradio 服务启动成功。 |
| HTTP 检查 | 通过 | `http://127.0.0.1:7860` 返回 `200`。 |
| `mamba run -n yolo python screenshot_ui.py` | 通过 | Playwright 默认 Chromium 缺失时成功 fallback 到系统浏览器并保存截图。 |
| `docs\ai-bridge\runtime-logs\capture_runtime_screenshots.py` | 通过 | 已更新 `docs/ai-bridge/screenshots/` 下 7 张截图。 |
| `git diff --check ...` | 通过 | 未发现空白错误；仅有 Git 的 CRLF 提示。 |

当前服务状态：

- 地址：`http://127.0.0.1:7860`
- HTTP：`200`
- 监听 PID：`52440`
- 命令：`python app.py --server-name 127.0.0.1 --server-port 7860`

## 6. check_model 路径不一致是否解决

已解决。

修复后 `scripts/check_model.py` 会在导入 `ultralytics` 前调用统一路径初始化函数，验证输出显示：

```text
ultralytics_source: E:\code\AI\YOLO\yolov8-train
status: ok
```

## 7. bat 日志误执行是否解决

已解决本次复现到的问题。

修复后重定向启动日志中没有再出现：

```text
is not recognized as an internal or external command
```

也没有出现乱码片段。启动日志为 ASCII 提示，服务正常启动并返回 HTTP 200。

## 8. 截图脚本 fallback 是否支持

已支持。

`screenshot_ui.py` 已在当前机器验证通过；在 Playwright 内置 Chromium 缺失的情况下，脚本成功使用系统浏览器完成截图。

## 9. 剩余问题

1. `docs/ai-bridge/runtime-logs/capture_runtime_screenshots.py` 仍是第二阶段临时取证脚本，当前能工作，但没有纳入正式脚本体系。
2. `app.py` 仍然较大，位置敏感输出较多，后续继续功能扩展时仍有维护风险。
3. 本阶段未做视觉布局优化，设置页模型路径信息密度较高的问题仍可在第四阶段处理。

## 10. 是否建议进入第四阶段

建议进入第四阶段 UI 和展示体验优化。

进入前提已经满足：`check_model.py` 自检恢复、启动脚本误执行日志消失、服务可启动且 HTTP 200、截图脚本具备系统浏览器 fallback、核心测试继续通过。
