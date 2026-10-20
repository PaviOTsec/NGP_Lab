# READ-ONLY: hMailServer log lines that carry credentials (must show ***), plus format samples.
$dir = 'C:\ProgramData\hMailServer\Logs'
Get-ChildItem $dir | ForEach-Object { "file: $($_.Name) $($_.Length) bytes" }
$log = Get-ChildItem $dir -Filter 'hmailserver_2*.log' | Sort-Object LastWriteTime | Select-Object -Last 1
"credential-bearing lines:"
Select-String -Path $log.FullName -Pattern 'RECEIVED: .*(AUTH|LOGIN|PASS |USER )|RECEIVED: [A-Za-z0-9+/=]{8,}\s*"?$' | ForEach-Object { "  $($_.Line)" } | Select-Object -First 12
"format samples (first line of each type):"
Get-Content $log.FullName | Group-Object { ($_ -split "`t")[0] } | ForEach-Object { "  [$($_.Count)] $($_.Group[0])" }
"awstats:"
Get-Content "$dir\hmailserver_awstats.log" -ErrorAction SilentlyContinue | Select-Object -Last 5 | ForEach-Object { "  $_" }
