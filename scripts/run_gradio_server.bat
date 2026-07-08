@echo off
chcp 65001 >nul
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI\"
call "%PROJECT_ROOT%scripts\project_config.bat"

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%"
cd /d "%PROJECT_ROOT%"
set "YOLO_CONFIG_DIR=%YOLO_CONFIG_DIR%"

if defined PYTHON_EXE (
    "%PYTHON_EXE%" app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%
) else (
    "%MAMBA_EXE%" run -n %MAMBA_ENV% python app.py --server-name %SERVER_NAME% --server-port %SERVER_PORT% %GRADIO_EXTRA_ARGS%
)
