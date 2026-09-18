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
$stdoutLog = Join-Path $logDirectory "gradio.stdout.log"
$stderrLog = Join-Path $logDirectory "gradio.stderr.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

# Keep the long-running command processor minimized while retaining diagnostics.
$runnerArguments = '/d /s /c ""{0}""' -f $runScriptPath
$runner = Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList $runnerArguments `
    -WorkingDirectory $projectRoot `
    -WindowStyle Minimized `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$exitedEarly = $runner.WaitForExit(1500)
if ($exitedEarly) {
    $runner.WaitForExit()
    $stderrTail = if (Test-Path -LiteralPath $stderrLog) {
        (Get-Content -LiteralPath $stderrLog -Tail 20) -join [Environment]::NewLine
    } else {
        ""
    }
    $message = "[ERROR] Background service runner exited immediately with code $($runner.ExitCode)."
    if ($stderrTail) {
        $message += [Environment]::NewLine + $stderrTail
    }
    throw $message
}

Write-Host ("[INFO] Background service runner PID: " + $runner.Id)
Write-Host ("[INFO] Service logs: " + $logDirectory)
