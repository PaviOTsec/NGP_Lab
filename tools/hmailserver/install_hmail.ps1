# Silent hMailServer install on L4H1_MailServer. __EXE__ is replaced by hmail.py.
# No /ADMINPASSWORD on the command line: Sysmon/4688 would record it. The password is set
# afterwards through the COM API (configure_hmail.ps1), which stores a hash in hMailServer.ini.
$ErrorActionPreference = 'Stop'
$exe = '__EXE__'
$log = 'C:\ProgramData\LabConsole\hmail\setup.log'
$svc = Get-CimInstance Win32_Service -Filter "Name='hMailServer'"
if ($svc) { "already installed: service $([string]$svc.State)"; return }
$p = Start-Process -FilePath $exe -Wait -PassThru -ArgumentList @(
  '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/LOG=`"$log`"", '/COMPONENTS="server,admintools"')
"setup exit code: $($p.ExitCode)"
$deadline = (Get-Date).AddSeconds(60)
do { Start-Sleep 3; $svc = Get-CimInstance Win32_Service -Filter "Name='hMailServer'" } until (($svc -and [string]$svc.State -eq 'Running') -or (Get-Date) -gt $deadline)
if ($svc) { "service: $([string]$svc.State) start=$([string]$svc.StartMode) as $($svc.StartName) path=$($svc.PathName)" } else { "service: NOT CREATED" }
"listening: " + ((Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq $svc.ProcessId } | ForEach-Object { "$($_.LocalAddress):$($_.LocalPort)" } | Sort-Object -Unique) -join ' ')
"setup log tail:"
Get-Content $log -Tail 15 | ForEach-Object { "  $_" }
