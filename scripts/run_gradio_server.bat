@echo off
chcp 65001 >nul
setlocal EnableExtensions
title YOLO Dental - Backend Console

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI\"
call "%PROJECT_ROOT%scripts\project_config.bat"

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%"
cd /d "%PROJECT_ROOT%"
set "YOLO_CONFIG_DIR=%YOLO_CONFIG_DIR%"
set "PYTHONUNBUFFERED=1"
set "PYTHONFAULTHANDLER=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [INFO] YOLO Dental backend console
echo [INFO] URL: http://%SERVER_NAME%:%SERVER_PORT%
echo [INFO] Closing this window stops the backend service.

if defined PYTHON_EXE (
    "%PYTHON_EXE%" -u "%PROJECT_ROOT%scripts\run_backend_console.py" app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%
) else (
    "%MAMBA_EXE%" run -n %MAMBA_ENV% python -u "%PROJECT_ROOT%scripts\run_backend_console.py" app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%
)
