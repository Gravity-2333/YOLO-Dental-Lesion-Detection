@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
call "%PROJECT_ROOT%scripts\project_config.bat"

echo [INFO] Project directory: %PROJECT_ROOT%
echo [INFO] Checking existing project process on port %SERVER_PORT%...
call "%PROJECT_ROOT%stop_project.bat" --from-start

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%"

echo [INFO] Starting Gradio frontend service...
echo [INFO] A backend log window will open. Close that window to stop the service.
start "YOLO Dental Gradio" "%ComSpec%" /k ""%PROJECT_ROOT%scripts\run_gradio_server.bat""

echo [INFO] Frontend URL: http://%SERVER_NAME%:%SERVER_PORT%
echo [INFO] If the page is not ready, wait a few seconds for model and Gradio startup.

endlocal
