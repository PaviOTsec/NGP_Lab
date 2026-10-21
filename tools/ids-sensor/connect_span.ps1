# CHANGE (operator-requested 2026-10-21): give L4H1_IDS the SPAN-aggregator feed on L4-HOST-1.
# The aggregator cable is in Embedded NIC 2 (Broadcom NetXtreme Gigabit Ethernet, 4C:C5:D9:E3:82:D0):
# the only connected physical NIC not in a SET team; it had only an APIPA address (no host use).
#   1. external vSwitch 'SPAN' on that NIC, no management OS adapter, no teaming
#   2. VM adapter 'capture' -> SPAN, port mirroring Destination, VLAN trunk (keep 802.1Q tags)
#   3. external port monitor mode = Source, so frames not addressed to a VM MAC reach the VM
# Every step read back and verified (CLAUDE.md rule 2). Rollback: tools/ids-sensor/README.md.
$ErrorActionPreference = 'Stop'
$vm = 'L4H1_IDS'; $sw = 'SPAN'; $nicDesc = 'Broadcom NetXtreme Gigabit Ethernet'; $nicMac = '4CC5D9E382D0'
$featureId = '776e0ba7-94a1-41c8-8f28-951f524251b5'   # Ethernet Switch Port Security Settings
$problems = @()

# 0. guard: the NIC is the one we identified, and not already bound
$port = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_ExternalEthernetPort |
        Where-Object { $_.ElementName -eq $nicDesc }
if (-not $port -or $port.PermanentAddress -ne $nicMac) { throw "NIC '$nicDesc' with MAC $nicMac not found" }

# 1. switch
$s = Get-VMSwitch -Name $sw -ErrorAction SilentlyContinue
if (-not $s) {
  if ($port.IsBound) { throw "'$nicDesc' is already bound to another switch" }
  $s = New-VMSwitch -Name $sw -NetAdapterInterfaceDescription $nicDesc -AllowManagementOS $false -EnableEmbeddedTeaming $false `
       -Notes 'SPAN aggregator feed for L4H1_IDS (Zeek/Suricata). Receive-only; no host or VM IPs. 2026-10-21.'
}
$s = Get-VMSwitch -Name $sw
if ([string]$s.SwitchType -ne 'External' -or $s.NetAdapterInterfaceDescription -ne $nicDesc -or $s.AllowManagementOS) {
  $problems += "switch: type=$([string]$s.SwitchType) nic=$($s.NetAdapterInterfaceDescription) mgmtOS=$($s.AllowManagementOS)"
}

# 2. VM adapter
Connect-VMNetworkAdapter -VMName $vm -Name 'capture' -SwitchName $sw
Set-VMNetworkAdapter -VMName $vm -Name 'capture' -PortMirroring Destination -Passthru | Out-Null
Set-VMNetworkAdapterVlan -VMName $vm -VMNetworkAdapterName 'capture' -Trunk -AllowedVlanIdList '1-4094' -NativeVlanId 1 -Passthru | Out-Null
$na = Get-VMNetworkAdapter -VMName $vm -Name 'capture'
$vl = Get-VMNetworkAdapterVlan -VMName $vm -VMNetworkAdapterName 'capture'
if ($na.SwitchName -ne $sw) { $problems += "capture switch=$($na.SwitchName)" }
if ([string]$na.PortMirroringMode -ne 'Destination') { $problems += "capture mirror=$([string]$na.PortMirroringMode)" }
if ([string]$vl.OperationMode -ne 'Trunk') { $problems += "capture vlan mode=$([string]$vl.OperationMode)" }

# 3. external port monitor mode (2 = Source)
$cur = Get-VMSwitchExtensionPortFeature -ExternalPort -SwitchName $sw -FeatureId $featureId -ErrorAction SilentlyContinue
if ($cur) {
  if ($cur.SettingData.MonitorMode -ne 2) { $cur.SettingData.MonitorMode = 2; Set-VMSwitchExtensionPortFeature -ExternalPort -SwitchName $sw -VMSwitchExtensionFeature $cur }
} else {
  $f = Get-VMSystemSwitchExtensionPortFeature -FeatureId $featureId
  $f.SettingData.MonitorMode = 2
  Add-VMSwitchExtensionPortFeature -ExternalPort -SwitchName $sw -VMSwitchExtensionFeature $f
}
$mon = (Get-VMSwitchExtensionPortFeature -ExternalPort -SwitchName $sw -FeatureId $featureId).SettingData.MonitorMode
if ($mon -ne 2) { $problems += "external port MonitorMode=$mon" }

# other VMs must not have landed on this switch
$others = @(Get-VM | Get-VMNetworkAdapter | Where-Object { $_.SwitchName -eq $sw -and $_.VMName -ne $vm })
if ($others.Count) { $problems += "other VMs on SPAN: $($others.VMName -join ',')" }

[pscustomobject]@{
  Switch = "{0} ({1}) on {2}, mgmtOS={3}" -f $s.Name, [string]$s.SwitchType, $s.NetAdapterInterfaceDescription, $s.AllowManagementOS
  Capture = "{0} -> {1}, mirror={2}, vlan={3} allowed={4} native={5}" -f $na.Name, $na.SwitchName, [string]$na.PortMirroringMode, [string]$vl.OperationMode, $vl.AllowedVlanIdListString, $vl.NativeVlanId
  ExternalPortMonitorMode = $mon
  Verified = ($problems.Count -eq 0)
  Problems = $problems
} | ConvertTo-Json
