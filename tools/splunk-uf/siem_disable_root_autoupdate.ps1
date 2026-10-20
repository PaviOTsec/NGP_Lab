# Run ON DMZH1_SIEM (elevated PowerShell), or push it with remote_ps.py.
# Why (2026-10-16): Splunk 10's KV store (kvstore-pdl sidecar) makes a local TLS call to the
# IPC broker with a ~9-10 s timeout. On this offline server Windows' certificate chain engine
# tries to download the Automatic Root Certificates list (ctldl.windowsupdate.com) during the
# verification; the DC's DNS takes ~7 s per internet name to fail, so the first verified
# handshake took 11.2 s and the KV store failed to start (status "failed", Security Essentials
# broken). Microsoft's documented setting for disconnected servers turns that download off.
# Same effect lab-wide via GPO: Computer Configuration > Administrative Templates > System >
# Internet Communication Management > Internet Communication settings >
# "Turn off Automatic Root Certificates Update" = Enabled.
$ErrorActionPreference = 'Stop'
$k = 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot'
$before = if (Test-Path $k) { (Get-ItemProperty $k -ErrorAction SilentlyContinue).DisableRootAutoUpdate } else { $null }
"before: key exists=$(Test-Path $k) DisableRootAutoUpdate=$(if ($null -eq $before) { '(not set)' } else { $before })"
if (-not (Test-Path $k)) { New-Item -Path $k -Force | Out-Null }
New-ItemProperty -Path $k -Name DisableRootAutoUpdate -PropertyType DWord -Value 1 -Force | Out-Null
$after = (Get-ItemProperty $k).DisableRootAutoUpdate
"after:  DisableRootAutoUpdate=$after"
if ($after -ne 1) { throw "read-back mismatch" }
"rollback: Remove-ItemProperty -Path '$k' -Name DisableRootAutoUpdate"
