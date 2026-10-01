$ErrorActionPreference = "Stop"

$taskName = "Establishment Census Exam Submission Sync"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runner = Join-Path $PSScriptRoot "run_submission_sync.ps1"
$powershell = Join-Path $PSHOME "powershell.exe"

if (-not (Test-Path $runner -PathType Leaf)) {
    throw "Sync runner was not found at $runner"
}

$service = New-Object -ComObject Schedule.Service
$service.Connect()
$definition = $service.NewTask(0)
$definition.RegistrationInfo.Description = "Synchronizes external exam submissions to the local Django database every minute."
$definition.Principal.UserId = "$env:USERDOMAIN\$env:USERNAME"
$definition.Principal.LogonType = 3
$definition.Principal.RunLevel = 0

$trigger = $definition.Triggers.Create(2)
$trigger.StartBoundary = (Get-Date).AddMinutes(1).ToString("s")
$trigger.DaysInterval = 1
$trigger.Repetition.Interval = "PT1M"
$trigger.Repetition.Duration = "P1D"
$trigger.Repetition.StopAtDurationEnd = $false
$trigger.Enabled = $true

$action = $definition.Actions.Create(0)
$action.Path = $powershell
$action.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`""
$action.WorkingDirectory = $projectRoot

$definition.Settings.MultipleInstances = 2
$definition.Settings.StartWhenAvailable = $true
$definition.Settings.ExecutionTimeLimit = "PT30M"
$definition.Settings.Enabled = $true
$definition.Settings.DisallowStartIfOnBatteries = $false
$definition.Settings.StopIfGoingOnBatteries = $false

$folder = $service.GetFolder("\")
[void]$folder.RegisterTaskDefinition(
    $taskName,
    $definition,
    6,
    "$env:USERDOMAIN\$env:USERNAME",
    $null,
    3,
    $null
)

$registeredTask = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
if ($registeredTask.State -eq "Unknown") {
    throw "Task Scheduler did not return a valid task after registration."
}

Write-Output "Registered '$taskName' to run every minute while this Windows user is logged in."
Write-Output "Project: $projectRoot"
Write-Output "Logs: $(Join-Path $projectRoot 'logs')"