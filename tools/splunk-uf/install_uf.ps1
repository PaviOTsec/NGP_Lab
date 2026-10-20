# Runs ON the target (sent by push_uf.py; placeholders __MSI__, __DS__, __LOCALSYSTEM__ are filled in).
# Installs the Splunk Universal Forwarder as a deployment client of the SIEM. No RECEIVING_INDEXER:
# outputs come from the deployment app lab_all_outputs, so the indexer address lives in one place.
# No admin password is passed on the command line (GENRANDOMPASSWORD); nobody logs into the UF.
$ErrorActionPreference = 'Stop'
$msi = '__MSI__'
$ds = '__DS__'
$log = Join-Path (Split-Path -Parent $msi) ("uf-install-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$msiArgs = @('/i', "`"$msi`"", 'AGREETOLICENSE=Yes', "DEPLOYMENT_SERVER=$ds", 'LAUNCHSPLUNK=1',
             'SERVICESTARTTYPE=auto', 'GENRANDOMPASSWORD=1', '/quiet', '/norestart', '/L*v', "`"$log`"")
if ('__LOCALSYSTEM__' -eq '1') { $msiArgs += 'USE_LOCAL_SYSTEM=1' }
$p = Start-Process -FilePath msiexec.exe -ArgumentList $msiArgs -Wait -PassThru
"msiexec exit code: $($p.ExitCode)   (log: $log)"
if ($p.ExitCode -notin 0, 3010) {
  Get-Content $log -Tail 400 | Select-String -Pattern 'Return value 3|error|Error \d+' | Select-Object -Last 15 | ForEach-Object { $_.Line }
  throw "msiexec failed with $($p.ExitCode)"
}
if ($p.ExitCode -eq 3010) { "NOTE: Windows asks for a reboot (3010); the forwarder runs anyway." }
$s = Get-CimInstance Win32_Service -Filter "Name='SplunkForwarder'"
"service: $([string]$s.State) as $($s.StartName) start=$([string]$s.StartMode)"
