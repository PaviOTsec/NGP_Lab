#Requires -RunAsAdministrator
# M2-S2 K2 on the kit's EWS VM: enable RDP (registry + firewall group), after saving the
# original state so ews_reset_k2.ps1 can restore it exactly. Reads every change back.
# DRAFT, untested. Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'

$stateDir = 'C:\ProgramData\M2S2'
$stateFile = Join-Path $stateDir 'k2-original.json'
$tsKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server'
$rdpGroup = '@FirewallAPI.dll,-28752'   # "Remote Desktop" rule group, locale-independent

if (Test-Path $stateFile) { throw "K2 already staged ($stateFile exists). Run ews_reset_k2.ps1 first." }
New-Item -ItemType Directory -Force $stateDir | Out-Null

$rules = Get-NetFirewallRule -Group $rdpGroup
$original = [pscustomobject]@{
    StagedAt           = (Get-Date).ToString('s')
    fDenyTSConnections = (Get-ItemProperty $tsKey).fDenyTSConnections
    TermServiceStatus  = [string](Get-Service TermService).Status
    Rules              = @($rules | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Enabled = [string]$_.Enabled } })
}
$original | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 $stateFile

Set-ItemProperty $tsKey -Name fDenyTSConnections -Value 0
$rules | Enable-NetFirewallRule
if ((Get-Service TermService).Status -ne 'Running') { Start-Service TermService }
Start-Sleep -Seconds 2

# Read back and verify: a call that returned no error is not proof it worked.
$deny = (Get-ItemProperty $tsKey).fDenyTSConnections
$disabled = @(Get-NetFirewallRule -Group $rdpGroup | Where-Object { [string]$_.Enabled -ne 'True' })
$listening = @(Get-NetTCPConnection -State Listen -LocalPort 3389 -ErrorAction SilentlyContinue)
if ($deny -ne 0 -or $disabled.Count -gt 0 -or $listening.Count -eq 0) {
    throw "K2 verify FAILED: fDenyTSConnections=$deny, rules still disabled=$($disabled.Count), listeners on 3389=$($listening.Count)"
}
"PASS: K2 staged at $($original.StagedAt). Original state saved to $stateFile"
