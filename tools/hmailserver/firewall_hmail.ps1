# Windows Firewall on L4H1_MailServer: allow the mail ports from lab subnets only (idempotent).
$ErrorActionPreference = 'Stop'
"profiles before: " + ((Get-NetFirewallProfile | ForEach-Object { "$($_.Name) enabled=$([string]$_.Enabled) in=$([string]$_.DefaultInboundAction)" }) -join '; ')
$existing = Get-NetFirewallPortFilter -Protocol TCP | Where-Object { @($_.LocalPort) | Where-Object { $_ -in '25', '110', '143', '587' } } |
  Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' }
"existing inbound rules on mail ports: " + $(if ($existing) { ($existing | ForEach-Object { "$($_.DisplayName)[$([string]$_.Action)]" }) -join ', ' } else { 'none' })
$name = 'LabConsole-hMailServer-Lab'
Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $name -DisplayName 'hMailServer SMTP/POP3/IMAP (lab subnets)' -Direction Inbound -Action Allow `
  -Protocol TCP -LocalPort 25, 110, 143, 587 -RemoteAddress 10.0.0.0/8, 192.168.0.0/16 -Profile Any | Out-Null
$r = Get-NetFirewallRule -Name $name
"rule: $($r.DisplayName) enabled=$([string]$r.Enabled) action=$([string]$r.Action) ports=" + (($r | Get-NetFirewallPortFilter).LocalPort -join ',') + " remote=" + (($r | Get-NetFirewallAddressFilter).RemoteAddress -join ',')
