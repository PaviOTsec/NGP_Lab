# READ-ONLY: hMailServer settings as the COM API sees them. Authenticates as Administrator
# with the real password if one is set (via __SECRETS__, deleted at the end), else empty.
$sf = '__SECRETS__'
try {
  $sec = Get-Content -Raw $sf | ConvertFrom-Json
  $app = New-Object -ComObject hMailServer.Application
  $acct = $app.Authenticate('Administrator', $sec.admin_password)
  $how = 'real password'
  if (-not $acct) { $acct = $app.Authenticate('Administrator', ''); $how = 'EMPTY password' }
  if (-not $acct) { throw 'cannot authenticate as Administrator' }
  "authenticated with: $how   version: $($app.Version) $($app.VersionArchitecture)"
  $s = $app.Settings
  "hostname: '$($s.HostName)'  defaultdomain: '$($s.DefaultDomain)'"
  "settings members (bool/string/int props):"
  ($s | Get-Member -MemberType Property | ForEach-Object Name) -join ', '
  "logging: " + (($s.Logging | Get-Member -MemberType Property | ForEach-Object { "$($_.Name)=$($s.Logging.($_.Name))" }) -join ' ')
  "tcpip ports:"
  for ($i = 0; $i -lt $s.TCPIPPorts.Count; $i++) { $p = $s.TCPIPPorts.Item($i); "  $([string]$p.Protocol) $($p.Address):$($p.PortNumber) ssl=$($p.UseSSL) starttls=$($p.ConnectionSecurity)" }
  "security ranges:"
  for ($i = 0; $i -lt $s.SecurityRanges.Count; $i++) {
    $r = $s.SecurityRanges.Item($i)
    "  -- " + (($r | Get-Member -MemberType Property | ForEach-Object { "$($_.Name)=$($r.($_.Name))" }) -join ' ')
  }
  "domains: " + (@(for ($i = 0; $i -lt $app.Domains.Count; $i++) { $app.Domains.Item($i).Name }) -join ', ')
  "account members: " + (($app.Domains | Get-Member -MemberType Method | ForEach-Object Name) -join ', ')
  "antispam: " + (($s.AntiSpam | Get-Member -MemberType Property | Where-Object { $_.Definition -match 'bool|int' } | ForEach-Object { "$($_.Name)=$($s.AntiSpam.($_.Name))" }) -join ' ')
  "ini: $($app.InitializationFile)"
  "timezone: $((Get-TimeZone).Id)  now: $(Get-Date -Format o)"
} finally { Remove-Item -LiteralPath $sf -Force -ErrorAction SilentlyContinue; "secrets file removed: $(-not (Test-Path $sf))" }
