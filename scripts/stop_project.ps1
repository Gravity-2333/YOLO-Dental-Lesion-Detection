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

$runnerPattern = [regex]::Escape((Join-Path $PSScriptRoot "run_gradio_server.bat"))
$runners = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID `
        -and $_.Name.ToLowerInvariant() -eq "cmd.exe" `
        -and $_.CommandLine `
        -and $_.CommandLine -match $runnerPattern
}

if (-not $items -and -not $runners) {
    exit 2
}

foreach ($item in $items) {
    Stop-Process -Id $item.ProcessId -Force -ErrorAction SilentlyContinue
    if (-not $Quiet) {
        Write-Host ("[INFO] Stopped process PID " + $item.ProcessId)
    }
}

# The console command runner is not matched by app.py's command line.
# Stop it explicitly so repeated restarts do not leave stale background processes.
foreach ($runner in $runners) {
    Stop-Process -Id $runner.ProcessId -Force -ErrorAction SilentlyContinue
    if (-not $Quiet) {
        Write-Host ("[INFO] Stopped backend console runner PID " + $runner.ProcessId)
    }
}

exit 0
