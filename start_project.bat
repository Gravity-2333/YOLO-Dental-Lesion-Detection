@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
call "%PROJECT_ROOT%scripts\project_config.bat"

echo [信息] 项目目录：%PROJECT_ROOT%
echo [信息] 正在检查端口 %SERVER_PORT% 上是否已有项目进程...
call "%PROJECT_ROOT%stop_project.bat" --from-start

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%"

if defined PYTHON_EXE (
    set "RUNNER="%PYTHON_EXE%" app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%"
) else (
    set "RUNNER=%MAMBA_EXE% run -n %MAMBA_ENV% python app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%"
)

echo [信息] 正在启动 Gradio 前端服务...
echo [信息] 新窗口会显示后端运行日志和可能的报错；关闭该窗口也会停止前端服务。
start "YOLO Dental Gradio" cmd /k "chcp 65001 >nul && cd /d "%PROJECT_ROOT%" && set "YOLO_CONFIG_DIR=%YOLO_CONFIG_DIR%" && %RUNNER%"

echo [信息] 前端访问地址：http://%SERVER_NAME%:%SERVER_PORT%
echo [信息] 如果页面暂时打不开，请等待几秒钟，模型和 Gradio 服务需要一点启动时间。

endlocal
