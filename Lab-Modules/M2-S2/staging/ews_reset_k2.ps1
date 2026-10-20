#Requires -RunAsAdministrator
# M2-S2 K2 reset on the kit's EWS VM: restore the exact pre-stage RDP state saved by
# ews_stage_k2.ps1, then read it back. DRAFT, untested. Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'

$stateFile = 'C:\ProgramData\M2S2\k2-original.json'
$tsKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server'

if (-not (Test-Path $stateFile)) { throw "No saved state at $stateFile; nothing to restore." }
$original = Get-Content -Raw $stateFile | ConvertFrom-Json

Set-ItemProperty $tsKey -Name fDenyTSConnections -Value ([int]$original.fDenyTSConnections)
foreach ($r in $original.Rules) {
    if ($r.Enabled -eq 'True') { Enable-NetFirewallRule -Name $r.Name } else { Disable-NetFirewallRule -Name $r.Name }
}
if ($original.TermServiceStatus -ne 'Running' -and (Get-Service TermService).Status -eq 'Running') {
    Stop-Service TermService -Force
}

# Read back and verify against the saved state.
$problems = @()
$deny = (Get-ItemProperty $tsKey).fDenyTSConnections
if ($deny -ne [int]$original.fDenyTSConnections) { $problems += "fDenyTSConnections=$deny" }
foreach ($r in $original.Rules) {
    $now = [string](Get-NetFirewallRule -Name $r.Name).Enabled
    if ($now -ne $r.Enabled) { $problems += "rule $($r.Name) Enabled=$now" }
}
if ($problems) { throw "K2 reset verify FAILED: $($problems -join '; ')" }

Remove-Item $stateFile
"PASS: K2 reset to the state saved at $($original.StagedAt)"
