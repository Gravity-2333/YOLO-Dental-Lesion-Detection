@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
call "%PROJECT_ROOT%scripts\project_config.bat"

if "%~1"=="--from-start" (
    set "QUIET=1"
) else (
    set "QUIET=0"
)

if "%QUIET%"=="1" (
    set "QUIET_ARG=-Quiet"
) else (
    set "QUIET_ARG="
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\stop_project.ps1" -Port "%SERVER_PORT%" %QUIET_ARG%

set "STOP_CODE=%ERRORLEVEL%"
if "%STOP_CODE%"=="2" (
    if "%QUIET%"=="0" echo [INFO] No project process found.
) else (
    if "%STOP_CODE%"=="0" (
        if "%QUIET%"=="0" echo [INFO] Project process stopped.
    ) else (
        echo [WARN] Stop command returned code: %STOP_CODE%.
    )
)

if "%QUIET%"=="0" pause
endlocal
