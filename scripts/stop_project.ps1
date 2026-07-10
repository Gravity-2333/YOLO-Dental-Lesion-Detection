param(
    [string]$Port = "7860",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

if (-not $Quiet) {
    Write-Host "[INFO] Checking Gradio project process on port $Port..."
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
    if (-not $Quiet) {
        Write-Host ("[INFO] Stopped process PID " + $item.ProcessId)
    }
}

exit 0
