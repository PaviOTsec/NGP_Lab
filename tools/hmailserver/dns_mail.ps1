# DMZH2_DC: A + MX records for the lab mail domain in the np.local zone (idempotent, read back).
$ErrorActionPreference = 'Stop'
$zone = 'np.local'; $name = 'mail'; $ip = '10.4.20.21'
"before: " + ((Get-DnsServerResourceRecord -ZoneName $zone -Name $name -ErrorAction SilentlyContinue | ForEach-Object { "$($_.RecordType) $($_.RecordData.IPv4Address)$($_.RecordData.MailExchange)" }) -join '; ')
if (-not (Get-DnsServerResourceRecord -ZoneName $zone -Name $name -RRType A -ErrorAction SilentlyContinue)) {
  Add-DnsServerResourceRecordA -ZoneName $zone -Name $name -IPv4Address $ip
}
if (-not (Get-DnsServerResourceRecord -ZoneName $zone -Name $name -RRType MX -ErrorAction SilentlyContinue)) {
  Add-DnsServerResourceRecordMX -ZoneName $zone -Name $name -MailExchange 'mail.np.local.' -Preference 10
}
"after: " + ((Get-DnsServerResourceRecord -ZoneName $zone -Name $name | ForEach-Object { "$($_.RecordType) $($_.RecordData.IPv4Address)$($_.RecordData.MailExchange) pref=$($_.RecordData.Preference)" }) -join '; ')
"resolve A: " + ((Resolve-DnsName mail.np.local -Type A -Server 127.0.0.1 -DnsOnly | Where-Object Type -eq A).IPAddress -join ',')
"resolve MX: " + ((Resolve-DnsName mail.np.local -Type MX -Server 127.0.0.1 -DnsOnly | Where-Object Type -eq MX).NameExchange -join ',')
