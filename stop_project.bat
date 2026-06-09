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

if "%QUIET%"=="0" echo [信息] 正在检查端口 %SERVER_PORT% 上的 Gradio 项目进程...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$port='%SERVER_PORT%';" ^
  "$names=@('python','python.exe','pythonw','pythonw.exe','mamba','mamba.exe','cmd','cmd.exe');" ^
  "$portPattern='--server-port(?:\s+|=)' + [regex]::Escape($port) + '(?:\s|$)';" ^
  "$items=Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $names -contains $_.ProcessName.ToLowerInvariant() -and $_.CommandLine -and $_.CommandLine -like '*app.py*' -and $_.CommandLine -match $portPattern };" ^
  "if (-not $items) { exit 2 };" ^
  "foreach ($item in $items) { Stop-Process -Id $item.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('[信息] 已关闭进程 PID ' + $item.ProcessId) }"

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
