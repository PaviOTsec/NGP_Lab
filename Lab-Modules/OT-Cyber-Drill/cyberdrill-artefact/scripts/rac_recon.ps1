$ErrorActionPreference = 'SilentlyContinue'

Write-Output "===== LOCAL ADMINS (who is admin on RAC) ====="
net localgroup administrators | Where-Object { $_ -and $_ -notmatch 'command completed|^Members|^----|^Alias|^Comment' }

Write-Output ""
Write-Output "===== LOGGED-ON / SESSIONS ====="
query user 2>$null
(quser 2>$null)

Write-Output ""
Write-Output "===== DEFENDER ====="
$mp = Get-MpComputerStatus
"RealTimeProtection : " + [string]$mp.RealTimeProtectionEnabled
"AMServiceEnabled   : " + [string]$mp.AMServiceEnabled
"TamperProtection   : " + [string]$mp.IsTamperProtected
"AntivirusEnabled   : " + [string]$mp.AntivirusEnabled

Write-Output ""
Write-Output "===== THIRD-PARTY AV / EDR SERVICES ====="
Get-Service | Where-Object { $_.Name -match 'mfe|trellix|masvc|mcafee|mpssvc|SentinelOne|CrowdStrike|cylance|carbonblack' } |
  ForEach-Object { "{0,-20} {1} ({2})" -f $_.Name,[string]$_.Status,$_.DisplayName }
try {
  Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct |
    ForEach-Object { "SecurityCenter AV : " + $_.displayName }
} catch {}

Write-Output ""
Write-Output "===== CREDENTIAL PROTECTIONS (matter for hash extraction) ====="
$ppl = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name RunAsPPL -ErrorAction SilentlyContinue).RunAsPPL
"RunAsPPL (LSA protection) : " + $(if ($null -eq $ppl) { 'not set (0)' } else { [string]$ppl })
$dg = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction SilentlyContinue
"DeviceGuard SvcsRunning   : " + [string]($dg.SecurityServicesRunning -join ',')  # 1=CredGuard, 2=HVCI
"DeviceGuard SvcsConfigured: " + [string]($dg.SecurityServicesConfigured -join ',')

Write-Output ""
Write-Output "===== OS / DOMAIN ====="
$cs = Get-CimInstance Win32_ComputerSystem
"Domain : " + [string]$cs.Domain + "  PartOfDomain: " + [string]$cs.PartOfDomain
(Get-CimInstance Win32_OperatingSystem).Caption
