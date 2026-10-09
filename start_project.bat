@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
call "%PROJECT_ROOT%scripts\project_config.bat"

echo [INFO] Project directory: %PROJECT_ROOT%
echo [INFO] Checking existing project process on port %SERVER_PORT%...
call "%PROJECT_ROOT%stop_project.bat" --from-start

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%"

echo [INFO] Starting Gradio service in a live backend console...
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%PROJECT_ROOT%scripts\start_project.ps1"
if errorlevel 1 (
    echo [ERROR] Failed to start the backend service.
    exit /b 1
)

echo [INFO] Frontend URL: http://%SERVER_NAME%:%SERVER_PORT%
echo [INFO] If the page is not ready, wait a few seconds for model and Gradio startup.

endlocal
