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
    if "%QUIET%"=="0" echo [信息] 当前没有发现可关闭的项目进程。
) else (
    if "%STOP_CODE%"=="0" (
        if "%QUIET%"=="0" echo [信息] 项目进程已关闭。
    ) else (
        echo [警告] 关闭命令返回异常代码：%STOP_CODE%。
    )
)

if "%QUIET%"=="0" pause
endlocal
