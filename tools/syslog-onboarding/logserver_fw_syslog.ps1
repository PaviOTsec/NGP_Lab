# DMZH1_LogServer (Scribbler): allow syslog UDP 514 inbound from the lab switches only.
# Idempotent (creates the rule, or updates its remote-address list); reads it back and prints it.
# Rollback: Remove-NetFirewallRule -Name 'LabConsole-Syslog-UDP514'
$name = 'LabConsole-Syslog-UDP514'
$remote = @('10.5.20.30', '10.4.20.30', '10.1.20.30', '192.168.30.30',   # SW-WAN, SW-Ent, SW-DMZ, SW-Ops (2026-10-19)
            '192.168.20.50', '192.168.1.30', '192.168.2.30', '192.168.3.30',  # SW-L2, SW-PCS, SW-SIS, SW-SAS (rule-13 exception 2026-10-19)
            '10.4.20.254', '10.1.20.254',                                  # FW-North (source-ip), FW-South (service route)
            '192.168.1.254', '192.168.20.254')                             # OT-FW vlan1 primary / secondary
if (-not (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $name -DisplayName 'Scribbler syslog UDP 514 (lab switches)' `
        -Description 'Added 2026-10-19 by Lab Console (syslog onboarding of SCALANCE switches).' `
        -Direction Inbound -Action Allow -Protocol UDP -LocalPort 514 -RemoteAddress $remote -Profile Any | Out-Null
} else {
    Get-NetFirewallRule -Name $name | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $remote
}
$r = Get-NetFirewallRule -Name $name
$p = $r | Get-NetFirewallPortFilter
$a = $r | Get-NetFirewallAddressFilter
"rule={0} enabled={1} action={2} dir={3} profile={4} proto={5} port={6} remote={7}" -f $r.Name, [string]$r.Enabled, [string]$r.Action, [string]$r.Direction, [string]$r.Profile, $p.Protocol, ($p.LocalPort -join ','), ($a.RemoteAddress -join ',')
