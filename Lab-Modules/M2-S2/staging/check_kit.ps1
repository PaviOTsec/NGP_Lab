# M2-S2 T-30 staging check, run on the kit's EWS VM after staging. Every line must say PASS.
# This is the workbook's "deviation scenario window is active". Read-only.
# DRAFT, untested; IPs are placeholders until M2S2-Q4. Windows PowerShell 5.1.
param(
    [Parameter(Mandatory)] [int]    $KitNumber,
    [Parameter(Mandatory)] [string] $KaliIp,
    [string] $Et200spIp = '192.168.10.11'   # drawing value, unconfirmed
)

$kaliMac = '08-00-27-4D-32-{0:D2}' -f $KitNumber

function Report([string]$name, [bool]$ok, [string]$detail) {
    '{0,-4} {1,-38} {2}' -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $name, $detail
}

# K2: RDP listening locally.
$rdp = @(Get-NetTCPConnection -State Listen -LocalPort 3389 -ErrorAction SilentlyContinue).Count -gt 0
Report 'K2 RDP listening on 3389' $rdp ''

# K1: Kali answers and has the expected MAC.
$null = Test-Connection $KaliIp -Count 2 -Quiet
$n = Get-NetNeighbor -IPAddress $KaliIp -ErrorAction SilentlyContinue | Select-Object -First 1
Report 'K1 Kali present with kit MAC' ($n -and $n.LinkLayerAddress -eq $kaliMac) "$KaliIp -> $($n.LinkLayerAddress)"

# K3 + K4: the ET 200SP's IP now resolves to Kali's MAC. Only meaningful if the EWS shares the
# ET 200SP's L2 segment (tracker G7); otherwise check on the switch's MAC table instead.
$null = Test-Connection $Et200spIp -Count 2 -Quiet
$e = Get-NetNeighbor -IPAddress $Et200spIp -ErrorAction SilentlyContinue | Select-Object -First 1
Report 'K3/K4 ET 200SP IP answered by Kali' ($e -and $e.LinkLayerAddress -eq $kaliMac) "$Et200spIp -> $($e.LinkLayerAddress)"
