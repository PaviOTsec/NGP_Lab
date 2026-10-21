# CHANGE (2026-10-20): after the autoinstall powered L4H1_IDS off - eject both ISOs, boot from the OS
# disk, verify (rule 2), start. Refuses unless the VM is Off.
$ErrorActionPreference = 'Stop'
$name = 'L4H1_IDS'
$v = Get-VM -Name $name
if ([string]$v.State -ne 'Off') { throw "VM is $([string]$v.State), expected Off (install still running?)" }
# by controller location, one at a time (piping the drive objects left the second one mounted, silently)
foreach ($d in @(Get-VMDvdDrive -VMName $name)) {
  Set-VMDvdDrive -VMName $name -ControllerNumber $d.ControllerNumber -ControllerLocation $d.ControllerLocation -Path $null -Passthru | Out-Null
}
$os = Get-VMHardDiskDrive -VMName $name | Where-Object { $_.Path -like '*-os.vhdx' }
Set-VMFirmware -VMName $name -FirstBootDevice $os -Passthru | Out-Null
$fw = Get-VMFirmware -VMName $name
$dv = @(Get-VMDvdDrive -VMName $name | Where-Object { $_.Path })
if ($dv.Count) { throw "DVD still mounted: $($dv.Path -join ', ')" }
if ($fw.BootOrder[0].Device.Path -ne $os.Path) { throw "first boot device is $($fw.BootOrder[0].Device.Path)" }
"DVDs ejected; first boot = $($os.Path)"
Start-VM -Name $name -Passthru | Out-Null
Start-Sleep 3
"state: $([string](Get-VM -Name $name).State)"
