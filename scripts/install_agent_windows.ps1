# DeviceShare per-user startup task; run in Windows PowerShell 5.1 or newer.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$AgentBinary,
  [Parameter(Mandatory=$true)][string]$Config
)
$ErrorActionPreference = 'Stop'
$binary = (Resolve-Path -LiteralPath $AgentBinary).Path
$configPath = (Resolve-Path -LiteralPath $Config).Path
if (-not (Test-Path -LiteralPath $binary -PathType Leaf) -or
    -not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
  throw 'Both the agent executable and agent config must exist.'
}
# Do not place the secret itself in command-line arguments.
if ($configPath.Contains('"')) { throw 'Config path cannot contain double quotes.' }
$workDir = Split-Path -Parent (Split-Path -Parent $configPath)
$action = New-ScheduledTaskAction -Execute $binary -Argument ('--config "' + $configPath + '"') -WorkingDirectory $workDir
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'DeviceShareAgent' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'DeviceShareAgent'
Write-Host 'DeviceShare Agent is registered for the current Windows user.'
Write-Host 'Check: Get-ScheduledTask -TaskName DeviceShareAgent'
Write-Host 'Remove: Unregister-ScheduledTask -TaskName DeviceShareAgent -Confirm:$false'
