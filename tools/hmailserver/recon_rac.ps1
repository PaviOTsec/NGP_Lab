# READ-ONLY: L4H1_RAC before Thunderbird goes on, and whether it can reach the mail server's ports.
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
"os: $($os.Caption) $($os.Version) $([string]$os.OSArchitecture)"
"host: $($cs.Name)  domain: $($cs.Domain)  logged-on: $($cs.UserName)"
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { "disk $($_.DeviceID) {0:N1} GB free" -f ($_.FreeSpace / 1GB) }
"profiles: " + ((Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special } | ForEach-Object { $_.LocalPath }) -join ', ')
$keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
"mail clients: " + ((Get-ItemProperty $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'thunderbird|outlook|office|mail' } | ForEach-Object { "$($_.DisplayName) $($_.DisplayVersion)" }) -join '; ')
"dns mail.np.local resolve: " + $(try { (Resolve-DnsName mail.np.local -ErrorAction Stop | Where-Object Type -eq 'A' | ForEach-Object IPAddress) -join ',' } catch { "none ($($_.Exception.Message))" })
"dns np.local MX: " + $(try { (Resolve-DnsName np.local -Type MX -ErrorAction Stop | Where-Object Type -eq 'MX' | ForEach-Object NameExchange) -join ',' } catch { "none" })
"tcp to 10.4.20.21 (refused = path open, nothing listening yet; timeout = blocked):"
foreach ($p in 25, 587, 143, 110, 3389) {
  $c = New-Object Net.Sockets.TcpClient
  try {
    $ar = $c.BeginConnect('10.4.20.21', $p, $null, $null)
    if (-not $ar.AsyncWaitHandle.WaitOne(3000)) { $r = 'timeout' }
    else { try { $c.EndConnect($ar); $r = 'open' } catch { $r = 'refused' } }
  } catch { $r = "error $($_.Exception.Message)" } finally { $c.Close() }
  "  $p : $r"
}
