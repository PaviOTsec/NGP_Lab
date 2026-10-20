# Runs ON a forwarder host (via tools\splunk-uf\remote_change.py).
# Why (2026-10-16): the UF runs as the least-privilege virtual account NT SERVICE\SplunkForwarder.
# The Sysmon channel's ACL only grants read to SY, BA, BO, SO and Event Log Readers (S-1-5-32-573),
# so the UF logs "Could not subscribe to Windows Event Log" for Microsoft-Windows-Sysmon/Operational.
# Splunk's documented fix: add the UF account to the local Event Log Readers group (read-only
# access to event logs), then restart the UF so its token carries the new group.
# Skips hosts where the UF runs as LocalSystem (e.g. the DC) - nothing to do there.
$ErrorActionPreference = 'Stop'
$svc = Get-CimInstance Win32_Service -Filter "Name='SplunkForwarder'"
if (-not $svc) { "no SplunkForwarder service - skipped"; return }
"UF account: $($svc.StartName)"
if ($svc.StartName -eq 'LocalSystem') { "runs as LocalSystem - can already read the Sysmon log, nothing to change"; return }
$grp = Get-LocalGroup -SID 'S-1-5-32-573'
$member = Get-LocalGroupMember -Group $grp -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'NT SERVICE\SplunkForwarder' }
if ($member) { "already a member of $($grp.Name)" } else {
  Add-LocalGroupMember -Group $grp -Member 'NT SERVICE\SplunkForwarder'
  if (-not (Get-LocalGroupMember -Group $grp | Where-Object { $_.Name -eq 'NT SERVICE\SplunkForwarder' })) { throw "read-back: not a member" }
  "added NT SERVICE\SplunkForwarder to $($grp.Name) (read-back ok)"
}
$uf = 'C:\Program Files\SplunkUniversalForwarder'
$log = "$uf\var\log\splunk\splunkd.log"; $off = (Get-Item $log).Length
$o = cmd /c "`"$uf\bin\splunk.exe`" restart 2>&1"; "UF restart: " + ((($o | Where-Object { $_ }) | Select-Object -Last 1))
Start-Sleep 45
$fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite'); try { if ($fs.Length -lt $off) { $off = 0 }; $null = $fs.Seek($off, 'Begin'); $t = (New-Object IO.StreamReader($fs)).ReadToEnd() } finally { $fs.Close() }
$err = @($t -split "`n" | Where-Object { $_ -match 'Sysmon' -and $_ -match 'ERROR' })
"Sysmon subscription errors since the restart: $($err.Count)"
$err | Select-Object -First 2 | ForEach-Object { '  ' + $_.Trim().Substring(0, [Math]::Min(220, $_.Trim().Length)) }
