<#
.SYNOPSIS
    Lab session launcher for MC01. Pick VMs from an inventory, open sessions.
    Credentials, SSH keys and the inventory live on a USB key (volume label LABKEY):

        <USB>:\lab\inventory.csv
        <USB>:\lab\creds\<name>.xml     (PSCredential via Export-Clixml - DPAPI-bound)
        <USB>:\lab\ssh\<keyfile>        (private keys for Linux guests)

    Usage (Windows PowerShell 5.1, MC01):
        . .\LabConnect.ps1
        Add-LabTrustedHosts            # once, elevated
        New-LabCredential -Name np-admin -UserName 'NP\Administrator'
        Connect-Lab                    # pick VMs, sessions land in $LabSessions
        Invoke-Command -Session (Get-LabSession) { hostname }
        Copy-Item .\file.zip -Destination C:\Staging\ -ToSession $LabSessions['DMZH2DC']
        Disconnect-Lab
#>

$script:UsbLabel = 'LABKEY'
if (-not $global:LabSessions) { $global:LabSessions = @{} }

function Get-LabKeyRoot {
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "VolumeName='$script:UsbLabel'" |
            Select-Object -First 1
    if (-not $disk) { throw "Lab key '$script:UsbLabel' is not connected." }
    $root = Join-Path ($disk.DeviceID + '\') 'lab'
    if (-not (Test-Path $root)) { throw "No \lab folder on $($disk.DeviceID)." }
    return $root
}

function Get-LabInventory {
    $root = Get-LabKeyRoot
    return @(Import-Csv (Join-Path $root 'inventory.csv'))
}

function New-LabCredential {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$UserName
    )
    $dir = Join-Path (Get-LabKeyRoot) 'creds'
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Get-Credential -UserName $UserName -Message "Lab credential '$Name'" |
        Export-Clixml -Path (Join-Path $dir "$Name.xml")
    Write-Host "Saved $Name (decryptable only by $env:USERNAME on $env:COMPUTERNAME)."
}

function Add-LabTrustedHosts {
    # Needs an elevated prompt. Appends Windows targets only, keeps existing entries.
    $current = (Get-Item WSMan:\localhost\Client\TrustedHosts).Value -split ',' |
               ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $missing = Get-LabInventory | Where-Object { $_.OS -eq 'Windows' -and $_.Address -notin $current } |
               Select-Object -ExpandProperty Address
    if (-not $missing) { Write-Host 'TrustedHosts already covers the inventory.'; return }
    Set-Item WSMan:\localhost\Client\TrustedHosts -Value ($missing -join ',') -Concatenate -Force
    (Get-Item WSMan:\localhost\Client\TrustedHosts).Value
}

function Select-LabTarget {
    param([object[]]$Items)
    if (Get-Command Out-GridView -ErrorAction SilentlyContinue) {
        return @($Items | Out-GridView -Title 'Select lab VMs (Ctrl/Shift for multiple)' -PassThru)
    }
    for ($i = 0; $i -lt $Items.Count; $i++) {
        '{0,3}  {1,-18} {2,-16} {3,-8} {4}' -f $i, $Items[$i].Name, $Items[$i].Address, $Items[$i].OS, $Items[$i].Segment
    }
    $pick = Read-Host 'Numbers, comma-separated'
    return @($pick -split ',' | Where-Object { $_.Trim() } | ForEach-Object { $Items[[int]$_.Trim()] })
}

function Connect-Lab {
    $root    = Get-LabKeyRoot
    $targets = Select-LabTarget (Get-LabInventory)
    if (-not $targets) { return }
    $credCache = @{}

    foreach ($t in $targets) {
        try {
            switch ($t.OS) {
                'Windows' {
                    if ($global:LabSessions[$t.Name] -and $global:LabSessions[$t.Name].State -eq 'Opened') {
                        Write-Host "[SKIP] $($t.Name) already open" -ForegroundColor DarkGray; continue
                    }
                    if (-not $credCache[$t.Credential]) {
                        $credCache[$t.Credential] = Import-Clixml (Join-Path $root "creds\$($t.Credential).xml")
                    }
                    $s = New-PSSession -ComputerName $t.Address -Credential $credCache[$t.Credential] `
                                       -Name $t.Name -ErrorAction Stop
                    $global:LabSessions[$t.Name] = $s
                    Write-Host "[OK]   $($t.Name)  ($($t.Address))" -ForegroundColor Green
                }
                'Linux' {
                    $key     = Join-Path $root "ssh\$($t.Credential)"
                    $sshArgs = "-i `"$key`" $($t.User)@$($t.Address)"
                    if (Get-Command wt.exe -ErrorAction SilentlyContinue) {
                        Start-Process wt.exe -ArgumentList "new-tab --title $($t.Name) ssh $sshArgs"
                    } else {
                        Start-Process ssh.exe -ArgumentList $sshArgs
                    }
                    Write-Host "[SSH]  $($t.Name)  ($($t.Address)) opened in new window" -ForegroundColor Cyan
                }
                default { Write-Host "[SKIP] $($t.Name): OS '$($t.OS)' not handled" -ForegroundColor Yellow }
            }
        } catch {
            Write-Host "[FAIL] $($t.Name): $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    $credCache.Clear()
}

function Get-LabSession {
    param([string[]]$Name)
    $all = $global:LabSessions.Values | Where-Object { $_.State -eq 'Opened' }
    if ($Name) { $all = $all | Where-Object { $_.Name -in $Name } }
    return @($all)
}

function Disconnect-Lab {
    $global:LabSessions.Values | Remove-PSSession -ErrorAction SilentlyContinue
    $global:LabSessions = @{}
    Write-Host 'All lab sessions closed.'
}
