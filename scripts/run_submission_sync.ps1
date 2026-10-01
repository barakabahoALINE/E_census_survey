$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$logDirectory = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDirectory ("submission-sync-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

if (-not (Test-Path $python -PathType Leaf)) {
    throw "Project virtual environment was not found at $python"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
"[$(Get-Date -Format o)] Starting submission sync" | Add-Content -Path $logFile

Push-Location $projectRoot
try {
    & $python manage.py sync_submissions *>> $logFile
    $exitCode = $LASTEXITCODE
} catch {
    $_ | Out-String | Add-Content -Path $logFile
    $exitCode = 1
} finally {
    Pop-Location
}

"[$(Get-Date -Format o)] Submission sync exited with code $exitCode" | Add-Content -Path $logFile
exit $exitCode