# CHANGE (operator-requested 2026-10-20): create the L4H1_IDS Ubuntu sensor VM on L4-HOST-1 as HyperVAdmin.
# Pulls the install ISO + CIDATA seed from MC01's temporary http.server (192.168.100.18:8088), checks
# SHA-256, builds the VM, and reads every setting back (CLAUDE.md rule 2). Does NOT start the VM.
# Placeholders __ISO_SHA__ / __SEED_SHA__ are filled in by the caller.
$ErrorActionPreference = 'Stop'
$name   = 'L4H1_IDS'
$root   = 'D:\Hyper-V\IDS-SENSOR'
$src    = 'http://192.168.100.18:8088'
$files  = @{ 'ubuntu-24.04.5-live-server-amd64.iso' = '__ISO_SHA__'; 'l4h1-ids-seed.iso' = '__SEED_SHA__' }

if (Get-VM -Name $name -ErrorAction SilentlyContinue) { throw "VM $name already exists - refusing to touch it" }
foreach ($f in $files.Keys) {
  $dst = Join-Path $root $f
  if (-not (Test-Path $dst) -or (Get-FileHash $dst -Algorithm SHA256).Hash -ne $files[$f]) {
    & curl.exe -sS -f -o $dst "$src/$f"; if ($LASTEXITCODE) { throw "download $f failed ($LASTEXITCODE)" }
  }
  $h = (Get-FileHash $dst -Algorithm SHA256).Hash
  if ($h -ne $files[$f]) { throw "$f hash mismatch: $h" }
  "staged $f sha256 OK"
}
Remove-Item (Join-Path $root 'probe.txt') -ErrorAction SilentlyContinue

$vm = New-VM -Name $name -Generation 2 -MemoryStartupBytes 32GB -Path $root `
      -NewVHDPath "$root\$name\Virtual Hard Disks\$name-os.vhdx" -NewVHDSizeBytes 80GB -SwitchName 'WAN'
$vm = Set-VM -VM $vm -ProcessorCount 12 -StaticMemory -AutomaticCheckpointsEnabled $false `
      -AutomaticStartAction Start -AutomaticStartDelay 120 -AutomaticStopAction ShutDown `
      -Notes 'Zeek + Suricata IDS sensor (Ubuntu 24.04). mgmt=WAN 10.5.20.60, capture NIC for the SPAN aggregator. Built from MC01 2026-10-20.' -Passthru

$mgmt = Get-VMNetworkAdapter -VM $vm
Rename-VMNetworkAdapter -VMNetworkAdapter $mgmt -NewName 'mgmt'
Set-VMNetworkAdapter -VMName $name -Name 'mgmt' -StaticMacAddress '00155DA981E0' -Passthru | Out-Null
Add-VMNetworkAdapter -VMName $name -Name 'capture' -StaticMacAddress '00155DA981E1' -Passthru | Out-Null   # left unconnected for the operator

$data = New-VHD -Path "$root\$name\Virtual Hard Disks\$name-data.vhdx" -SizeBytes 500GB -Dynamic
Add-VMHardDiskDrive -VMName $name -Path $data.Path -Passthru | Out-Null
$dvd  = Add-VMDvdDrive -VMName $name -Path "$root\ubuntu-24.04.5-live-server-amd64.iso" -Passthru
Add-VMDvdDrive -VMName $name -Path "$root\l4h1-ids-seed.iso" -Passthru | Out-Null
Set-VMFirmware -VMName $name -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority -FirstBootDevice $dvd -Passthru | Out-Null
Enable-VMIntegrationService -VMName $name -Name 'Guest Service Interface' -Passthru | Out-Null

# ---- read back and verify
$v  = Get-VM -Name $name
$fw = Get-VMFirmware -VMName $name
$na = @(Get-VMNetworkAdapter -VMName $name | ForEach-Object { [pscustomobject]@{ Name=$_.Name; Switch=[string]$_.SwitchName; Mac=$_.MacAddress; Dynamic=$_.DynamicMacAddressEnabled } })
$hd = @(Get-VMHardDiskDrive -VMName $name | ForEach-Object { $x = Get-VHD -Path $_.Path; [pscustomobject]@{ Path=$_.Path; SizeGB=[math]::Round($x.Size/1GB); Type=[string]$x.VhdType } })
$dv = @(Get-VMDvdDrive -VMName $name | ForEach-Object { $_.Path })
$problems = @()
if ($v.ProcessorCount -ne 12) { $problems += "vCPU=$($v.ProcessorCount)" }
if ($v.MemoryStartup -ne 32GB -or $v.DynamicMemoryEnabled) { $problems += "memory" }
if ($v.AutomaticCheckpointsEnabled) { $problems += "auto-checkpoints on" }
if ([string]$fw.SecureBoot -ne 'On' -or $fw.SecureBootTemplate -ne 'MicrosoftUEFICertificateAuthority') { $problems += "secureboot $([string]$fw.SecureBoot)/$($fw.SecureBootTemplate)" }
if ([string]$fw.BootOrder[0].Device.Path -notlike '*ubuntu-24.04.5*') { $problems += "first boot device" }
if (($na | Where-Object Name -eq 'mgmt').Switch -ne 'WAN' -or ($na | Where-Object Name -eq 'mgmt').Mac -ne '00155DA981E0') { $problems += "mgmt nic" }
if (($na | Where-Object Name -eq 'capture').Switch -or ($na | Where-Object Name -eq 'capture').Mac -ne '00155DA981E1') { $problems += "capture nic" }
if ($hd.Count -ne 2 -or $dv.Count -ne 2) { $problems += "disks/dvd" }
[pscustomobject]@{
  Name=$v.Name; State=[string]$v.State; vCPU=$v.ProcessorCount; MemoryGB=$v.MemoryStartup/1GB; Dynamic=$v.DynamicMemoryEnabled
  AutoCheckpoints=$v.AutomaticCheckpointsEnabled; StartAction=[string]$v.AutomaticStartAction; StopAction=[string]$v.AutomaticStopAction
  SecureBoot=[string]$fw.SecureBoot; Template=$fw.SecureBootTemplate; FirstBoot=[string]$fw.BootOrder[0].Device.Path
  NICs=$na; Disks=$hd; DVD=$dv; Verified=($problems.Count -eq 0); Problems=$problems
} | ConvertTo-Json -Depth 4
