[CmdletBinding()]
param(
    [string]$RunScript
)

$ErrorActionPreference = "Stop"

$RunScript = if ($RunScript) {
    $RunScript
} else {
    Join-Path $PSScriptRoot "run_gradio_server.bat"
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runScriptPath = (Resolve-Path $RunScript).Path
$logDirectory = Join-Path $projectRoot "logs"
$stderrLog = Join-Path $logDirectory "gradio.stderr.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

# Resolve the environment interpreter once so the long-running service is not
# hosted beneath `mamba run`, which makes native Windows failures harder to diagnose.
$configPath = Join-Path $PSScriptRoot "project_config.bat"
if (-not $env:PYTHON_EXE -and (Test-Path -LiteralPath $configPath)) {
    $probe = & $env:ComSpec /d /s /c "`"$configPath`" && `"%MAMBA_EXE%`" run -n %MAMBA_ENV% python -c `"import sys; print(sys.executable)`"" 2>$null
    $candidate = $probe | Where-Object { $_ -and (Test-Path -LiteralPath $_.Trim()) } | Select-Object -Last 1
    if ($candidate) {
        $env:PYTHON_EXE = $candidate.Trim()
    }
}

# The runner mirrors output to the console and logs. Do not redirect its streams,
# which would leave the visible backend window empty again.
$runnerArguments = '/d /s /c ""{0}""' -f $runScriptPath
$runner = Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList $runnerArguments `
    -WorkingDirectory $projectRoot `
    -WindowStyle Normal `
    -PassThru

$exitedEarly = $runner.WaitForExit(1500)
if ($exitedEarly) {
    $runner.WaitForExit()
    $stderrTail = if (Test-Path -LiteralPath $stderrLog) {
        (Get-Content -LiteralPath $stderrLog -Tail 20) -join [Environment]::NewLine
    } else {
        ""
    }
    $message = "[ERROR] Backend console runner exited immediately with code $($runner.ExitCode)."
    if ($stderrTail) {
        $message += [Environment]::NewLine + $stderrTail
    }
    throw $message
}

Write-Host ("[INFO] Backend console runner PID: " + $runner.Id)
Write-Host ("[INFO] Service logs: " + $logDirectory)
