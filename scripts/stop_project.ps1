param(
    [string]$Port = "7860",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

if (-not $Quiet) {
    Write-Host "[信息] 正在检查端口 $Port 上的 Gradio 项目进程..."
}

$processNames = @("python.exe", "pythonw.exe", "mamba.exe", "cmd.exe", "python", "pythonw", "mamba", "cmd")
$escapedPort = [regex]::Escape($Port)
$portPattern = "--server-port(?:\s+|=)$escapedPort(?:\s|$)"

$items = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID `
        -and $processNames -contains $_.Name.ToLowerInvariant() `
        -and $_.CommandLine `
        -and $_.CommandLine -like "*app.py*" `
        -and $_.CommandLine -match $portPattern
}

if (-not $items) {
    exit 2
}

foreach ($item in $items) {
    Stop-Process -Id $item.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host ("[信息] 已关闭进程 PID " + $item.ProcessId)
}

exit 0
