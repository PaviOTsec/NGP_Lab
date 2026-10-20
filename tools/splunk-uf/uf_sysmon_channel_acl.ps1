# Runs ON a forwarder host that has no local "Event Log Readers" group (DMZH2_ADWSUS, 2026-10-16:
# several BUILTIN groups are missing there). Grants ONLY the UF's virtual account read (0x1) on
# the Sysmon channel, then restarts the UF. A Sysmon reinstall may reset the channel ACL - re-run.
$ErrorActionPreference = 'Stop'
$ch = 'Microsoft-Windows-Sysmon/Operational'
$sid = (New-Object Security.Principal.NTAccount('NT SERVICE\SplunkForwarder')).Translate([Security.Principal.SecurityIdentifier]).Value
"UF virtual account SID: $sid"
$acl = ((cmd /c "wevtutil gl $ch 2>&1") | Select-String 'channelAccess:\s*(.+)$').Matches[0].Groups[1].Value.Trim()
"before: $acl"
if ($acl -match [regex]::Escape(";;;$sid)")) { "already granted" } else {
  $new = "$acl(A;;0x1;;;$sid)"
  $o = cmd /c "wevtutil sl $ch /ca:$new 2>&1"
  if ($LASTEXITCODE -ne 0) { throw "wevtutil sl failed: $o" }
  $after = ((cmd /c "wevtutil gl $ch 2>&1") | Select-String 'channelAccess:\s*(.+)$').Matches[0].Groups[1].Value.Trim()
  "after:  $after"
  if ($after -ne $new) { throw "read-back mismatch" }
  "rollback: wevtutil sl $ch /ca:$acl"
}
$uf = 'C:\Program Files\SplunkUniversalForwarder'
$log = "$uf\var\log\splunk\splunkd.log"; $off = (Get-Item $log).Length
$o = cmd /c "`"$uf\bin\splunk.exe`" restart 2>&1"; "UF restart: " + ((($o | Where-Object { $_ }) | Select-Object -Last 1))
Start-Sleep 45
$fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite'); try { if ($fs.Length -lt $off) { $off = 0 }; $null = $fs.Seek($off, 'Begin'); $t = (New-Object IO.StreamReader($fs)).ReadToEnd() } finally { $fs.Close() }
"Sysmon subscription errors since the restart: " + @($t -split "`n" | Where-Object { $_ -match 'Sysmon' -and $_ -match 'ERROR' }).Count
