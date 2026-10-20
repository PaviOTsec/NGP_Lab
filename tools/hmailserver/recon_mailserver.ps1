# READ-ONLY: what is on L4H1_MailServer before hMailServer goes on.
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
"os: $($os.Caption) $($os.Version) $([string]$os.OSArchitecture)"
"host: $($cs.Name)  domain: $($cs.Domain)  partOfDomain: $($cs.PartOfDomain)"
"ram: {0:N1} GB total, {1:N1} GB free" -f ($os.TotalVisibleMemorySize / 1MB), ($os.FreePhysicalMemory / 1MB)
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { "disk $($_.DeviceID) {0:N1} GB free of {1:N1}" -f ($_.FreeSpace / 1GB), ($_.Size / 1GB) }
"ip: " + ((Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' | ForEach-Object { "$($_.IPAddress -join ',') gw=$($_.DefaultIPGateway -join ',') dns=$($_.DNSServerSearchOrder -join ',')" }) -join ' | ')
$net = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue
"dotnet4 release: $($net.Release)"
$n35 = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v3.5' -ErrorAction SilentlyContinue
"dotnet3.5 installed: $($n35.Install)"
"listening (mail-ish ports):"
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 25, 110, 143, 465, 587, 993, 995, 80, 443 } |
  ForEach-Object { "  $($_.LocalAddress):$($_.LocalPort) pid=$($_.OwningProcess) $((Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName)" }
"installed software (mail/db related):"
$keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
Get-ItemProperty $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'mail|smtp|sql|exchange|splunk|sysmon|\.NET' } |
  ForEach-Object { "  $($_.DisplayName) $($_.DisplayVersion)" } | Sort-Object -Unique
"windows features (smtp/web):"
try { Get-WindowsFeature -Name SMTP-Server, Web-Server, NET-Framework-Core -ErrorAction Stop | ForEach-Object { "  $($_.Name): $([string]$_.InstallState)" } } catch { "  Get-WindowsFeature unavailable: $($_.Exception.Message)" }
"firewall profiles: " + ((Get-NetFirewallProfile | ForEach-Object { "$($_.Name)=$([string]$_.Enabled)" }) -join ' ')
"splunk uf inputs dir:"
Get-ChildItem 'C:\Program Files\SplunkUniversalForwarder\etc\apps' -Directory -ErrorAction SilentlyContinue | ForEach-Object { "  $($_.Name)" }
