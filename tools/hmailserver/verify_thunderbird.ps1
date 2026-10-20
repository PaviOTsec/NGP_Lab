# L4H1_RAC: start Thunderbird headless in a throwaway profile and check that mozilla.cfg created
# the preset account (IMAP folder dir + an IMAP connection attempt). Cleans up after itself.
$dir = 'C:\Program Files\Mozilla Thunderbird'
$prof = 'C:\ProgramData\LabConsole\hmail\tbtest'
$userTB = Join-Path $env:APPDATA 'Thunderbird'; $hadUserTB = Test-Path $userTB
Remove-Item $prof -Recurse -Force -ErrorAction SilentlyContinue
$p = Start-Process "$dir\thunderbird.exe" -ArgumentList '-headless', '-no-remote', '-profile', "`"$prof`"" -PassThru
Start-Sleep 30
Get-CimInstance Win32_Process -Filter "Name='thunderbird.exe'" | Where-Object { $_.CommandLine -match 'tbtest' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 2
"profile dirs: " + ((Get-ChildItem $prof -Directory -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', ')
"ImapMail: " + ((Get-ChildItem "$prof\ImapMail" -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', ')
"Mail: " + ((Get-ChildItem "$prof\Mail" -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', ')
"prefs.js mail lines:"
Get-Content "$prof\prefs.js" -ErrorAction SilentlyContinue | Where-Object { $_ -match 'mail\.(server|account|identity|smtp|outgoing)' } | ForEach-Object { "  $_" } | Select-Object -First 25
Remove-Item $prof -Recurse -Force -ErrorAction SilentlyContinue
if (-not $hadUserTB) { Remove-Item $userTB -Recurse -Force -ErrorAction SilentlyContinue }
"cleaned up: profile=$(-not (Test-Path $prof)) userdir-restored=$((Test-Path $userTB) -eq $hadUserTB)"
