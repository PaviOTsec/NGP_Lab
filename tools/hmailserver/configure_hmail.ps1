# Configure hMailServer on L4H1_MailServer (idempotent). Passwords come from __SECRETS__ (copied
# over SMB by hmail.py, deleted here) so they never appear in script text / PowerShell logging.
# Every change is read back afterwards and printed.
$ErrorActionPreference = 'Stop'
$sf = '__SECRETS__'
$domainName = 'mail.np.local'
try {
  $sec = Get-Content -Raw $sf | ConvertFrom-Json
  $app = New-Object -ComObject hMailServer.Application

  # --- Administrator password (empty right after install) ---
  if ($app.Authenticate('Administrator', $sec.admin_password)) { "admin password: already set" }
  elseif ($app.Authenticate('Administrator', '')) {
    $app.Settings.SetAdministratorPassword($sec.admin_password)
    $app = New-Object -ComObject hMailServer.Application
    if (-not $app.Authenticate('Administrator', $sec.admin_password)) { throw 'new admin password does not authenticate' }
    if ((New-Object -ComObject hMailServer.Application).Authenticate('Administrator', '')) { throw 'empty admin password still accepted' }
    "admin password: set and verified (empty password now refused)"
  } else { throw 'cannot authenticate as Administrator' }
  $s = $app.Settings

  # --- Server identity + logging ---
  # No MaskPasswordsInLog: it is a no-op in 5.7 (reads back False). 5.7 masks SMTP AUTH / IMAP
  # LOGIN / POP3 PASS unconditionally (PasswordRemover); checked on the live log by verify step.
  $s.HostName = $domainName
  $s.DefaultDomain = $domainName          # lets users log in as plain "student1"
  $l = $s.Logging
  $l.LogApplication = $true; $l.LogSMTP = $true; $l.LogPOP3 = $true; $l.LogIMAP = $true; $l.LogTCPIP = $true
  $l.LogDebug = $false; $l.AWStatsEnabled = $true; $l.KeepFilesOpen = $false
  $l.Enabled = $true

  # --- IP ranges: lab subnets only, no relay; everything else refused ---
  function Set-Range($name, $lo, $hi, $prio, [bool]$allow) {
    $rs = $s.SecurityRanges; $r = $null
    for ($i = 0; $i -lt $rs.Count; $i++) { $x = $rs.Item($i); if ($x.Name -eq $name -or ($name -like 'Outside*' -and $x.Name -eq 'Internet')) { $r = $x } }
    if (-not $r) { $r = $rs.Add() }
    $r.Name = $name; $r.LowerIP = $lo; $r.UpperIP = $hi; $r.Priority = $prio
    $r.AllowSMTPConnections = $allow; $r.AllowPOP3Connections = $allow; $r.AllowIMAPConnections = $allow
    $r.AllowDeliveryFromLocalToLocal = $allow; $r.AllowDeliveryFromRemoteToLocal = $allow
    $r.AllowDeliveryFromLocalToRemote = $false; $r.AllowDeliveryFromRemoteToRemote = $false
    $r.RequireSMTPAuthLocalToLocal = $true; $r.RequireSMTPAuthLocalToExternal = $true
    $r.RequireSMTPAuthExternalToLocal = $false; $r.RequireSMTPAuthExternalToExternal = $true
    $r.RequireSSLTLSForAuth = $false; $r.IsForwardingRelay = $false; $r.Expires = $false
    $r.Save()
  }
  Set-Range 'Lab networks 10.0.0.0/8' '10.0.0.0' '10.255.255.255' 20 $true
  Set-Range 'Lab networks 192.168.0.0/16' '192.168.0.0' '192.168.255.255' 20 $true
  Set-Range 'Outside lab (refused)' '0.0.0.0' '255.255.255.255' 10 $false

  # --- Domain + accounts ---
  $d = $null
  for ($i = 0; $i -lt $app.Domains.Count; $i++) { if ($app.Domains.Item($i).Name -eq $domainName) { $d = $app.Domains.Item($i) } }
  if (-not $d) { $d = $app.Domains.Add(); $d.Name = $domainName }
  $d.Active = $true; $d.Save()
  foreach ($p in $sec.accounts.PSObject.Properties) {
    $acc = $null
    for ($i = 0; $i -lt $d.Accounts.Count; $i++) { if ($d.Accounts.Item($i).Address -eq $p.Name) { $acc = $d.Accounts.Item($i) } }
    if (-not $acc) { $acc = $d.Accounts.Add(); $acc.Address = $p.Name }
    $acc.Password = $p.Value; $acc.Active = $true; $acc.MaxSize = 1024; $acc.AdminLevel = 0
    $acc.Save()
  }
  $s.Logging.Enabled = $true

  # --- Read back (fresh session) ---
  $app = New-Object -ComObject hMailServer.Application
  $null = $app.Authenticate('Administrator', $sec.admin_password)
  $s = $app.Settings; $l = $s.Logging
  "hostname=$($s.HostName) defaultdomain=$($s.DefaultDomain)"
  "logging: Enabled=$($l.Enabled) App=$($l.LogApplication) SMTP=$($l.LogSMTP) POP3=$($l.LogPOP3) IMAP=$($l.LogIMAP) TCPIP=$($l.LogTCPIP) AWStats=$($l.AWStatsEnabled) Debug=$($l.LogDebug)"
  "autoban: OnLogonFailure=$($s.AutoBanOnLogonFailure) attempts=$($s.MaxInvalidLogonAttempts) within=$($s.MaxInvalidLogonAttemptsWithin)min ban=$($s.AutoBanMinutes)min"
  for ($i = 0; $i -lt $s.SecurityRanges.Count; $i++) {
    $r = $s.SecurityRanges.Item($i)
    "range '$($r.Name)' $($r.LowerIP)-$($r.UpperIP) prio=$($r.Priority) conn(smtp/pop/imap)=$($r.AllowSMTPConnections)/$($r.AllowPOP3Connections)/$($r.AllowIMAPConnections) relay(L>R,R>R)=$($r.AllowDeliveryFromLocalToRemote)/$($r.AllowDeliveryFromRemoteToRemote) authL>L=$($r.RequireSMTPAuthLocalToLocal)"
  }
  for ($i = 0; $i -lt $app.Domains.Count; $i++) {
    $d = $app.Domains.Item($i)
    "domain $($d.Name) active=$($d.Active) accounts=$($d.Accounts.Count)"
    for ($j = 0; $j -lt $d.Accounts.Count; $j++) { $a = $d.Accounts.Item($j); "  $($a.Address) active=$($a.Active) maxMB=$($a.MaxSize) adminlevel=$($a.AdminLevel)" }
  }
  try {
    $bad = @($sec.accounts.PSObject.Properties | Where-Object { -not $app.Domains.ItemByName($domainName).Accounts.ItemByAddress($_.Name).ValidatePassword($_.Value) } | ForEach-Object Name)
    "password check: " + $(if ($bad.Count) { "MISMATCH for $($bad -join ', ')" } else { "all $(@($sec.accounts.PSObject.Properties).Count) accounts accept their password" })
  } catch { "password check via COM unavailable ($($_.Exception.Message)); verified by IMAP login instead" }
} finally { Remove-Item -LiteralPath $sf -Force -ErrorAction SilentlyContinue; "secrets file removed: $(-not (Test-Path $sf))" }
