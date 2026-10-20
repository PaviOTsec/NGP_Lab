# Scribbler -> Splunk bridge (docs/SPLUNK_SCRIBBLER_PLAN.md). Runs on DMZH1_LogServer as a UF
# scripted input every 60 s. READ-ONLY towards Scribbler: it only calls _search, _mapping and
# _pit on the local Elasticsearch (127.0.0.1:9200) and never changes Scribbler.
#
# Each run reads the stored syslog documents in the half-open window [checkpoint, now - 60 s)
# (sorted by @timestamp, paged with a point-in-time + search_after), classifies each one by
# vendor, appends one line per document to <out>\<vendor>\<vendor>-yyyyMMdd.log (UTF-8, no BOM)
# and only then advances the checkpoint. The UF monitors those folders (one sourcetype each).
# Line format: "<@timestamp yyyy-MM-ddTHH:mm:ss.fffZ> <hostIp> <body>" - no commas before the
# body, so the Palo Alto add-on's comma-counting extractions still line up.
# stdout = one JSON heartbeat per run (sourcetype scribbler:bridge); nothing else is printed.
#
#   -DryRun   : write nothing, print up to -Preview lines per vendor + the heartbeat.
#   -From     : window start (ISO, UTC) instead of the checkpoint - for dry runs only.
param([switch]$DryRun, [int]$Preview = 20, [string]$From)

$ErrorActionPreference = 'Stop'
$Es = 'http://127.0.0.1:9200'
$Pattern = 'scribbler*'
$LagSec = 60                      # leave the newest minute for Logstash / ES refresh to settle
$MaxWindowHours = 24              # backfill moves forward at most this much per run
$PageSize = 500                   # keeps each response small for PS 5.1 ConvertFrom-Json
$KeepDays = 7
$SplunkHome = if ($env:SPLUNK_HOME) { $env:SPLUNK_HOME } else { 'C:\Program Files\SplunkUniversalForwarder' }
$StateDir = Join-Path $SplunkHome 'var\lib\lab_scribbler_bridge'
$OutDir = Join-Path $SplunkHome 'var\lib\lab_scribbler_bridge_out'
$StateFile = Join-Path $StateDir 'checkpoint.json'
$Vendors = 'scalance', 'fortigate', 'paloalto', 'scribbler', 'unknown'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Invoke-Es([string]$Method, [string]$Path, $Body) {
    $p = @{ UseBasicParsing = $true; Method = $Method; Uri = "$Es/$Path"; TimeoutSec = 60 }
    if ($null -ne $Body) {
        $p.ContentType = 'application/json; charset=utf-8'
        $p.Body = $Utf8.GetBytes(($Body | ConvertTo-Json -Depth 10 -Compress))
    }
    $r = Invoke-WebRequest @p
    # decode as UTF-8 ourselves: PS 5.1 falls back to ISO-8859-1 when no charset is sent
    $Utf8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
}

function Format-Ts([string]$s) {
    [DateTime]::Parse($s, [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal
    ).ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", [Globalization.CultureInfo]::InvariantCulture)
}

function Get-Vendor($s) {
    $msg = [string]$s.message
    if (([string]$s.syslog_program).StartsWith('6GK5')) { return 'scalance' }      # switches + OT-FW (SC646)
    if ($msg -match '\bdevid="?F' -and $msg -match '\blogid="?\d') { return 'fortigate' }
    if ($msg -match '^[^,]*,[^,]*,[^,]*,(TRAFFIC|THREAT|SYSTEM|CONFIG|HIPMATCH|CORRELATION|USERID|GLOBALPROTECT|DECRYPTION),') { return 'paloalto' }
    if ($s.hostIp -eq '127.0.0.1' -and $msg -match '"Application"\s*:\s*"ScribblerLogManager"') { return 'scribbler' }
    'unknown'
}

function Format-Line($s, [string]$vendor) {
    $msg = ([string]$s.message) -replace '[\r\n]+', ' '
    $msg = $msg.Trim()
    $head = (Format-Ts ([string]$s.'@timestamp')) + ' ' + [string]$s.hostIp + ' '
    if ($vendor -eq 'scalance') {
        return $head + ('sev={0} fac={1} prog={2} msg={3}' -f $s.syslog_severity_code, $s.syslog_facility_code, $s.syslog_program, $msg)
    }
    $head + $msg
}

$hb = [ordered]@{ status = 'ok'; es_ok = $false; dry_run = [bool]$DryRun; window_from = $null; window_to = $null
                  fetched = 0; by_vendor = [ordered]@{}; error = $null }
$pit = $null
try {
    # schema check: the fields this bridge depends on must still exist (a Scribbler upgrade could change them)
    $map = Invoke-Es 'GET' "$Pattern/_mapping/field/hostIp,message,@timestamp" $null
    $seen = @{}
    foreach ($ix in $map.PSObject.Properties) { foreach ($f in $ix.Value.mappings.PSObject.Properties) { $seen[$f.Name] = $true } }
    $missing = @('hostIp', 'message', '@timestamp' | Where-Object { -not $seen[$_] })
    if ($missing.Count) { throw "Scribbler schema changed: missing field(s) $($missing -join ', ')" }
    $hb.es_ok = $true

    # window (PowerShell names are case-insensitive: $winFrom must not be called $from, that is the -From parameter)
    $now = [DateTime]::UtcNow
    $winTo = $now.AddSeconds(-$LagSec)
    if ($From) {
        if (-not $DryRun) { throw '-From is for dry runs only' }
        $winFrom = [DateTime]::Parse($From, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal)
    } elseif (Test-Path -LiteralPath $StateFile) {
        $winFrom = [DateTime]::Parse((Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json).next_from,
            [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal)
    } else {
        $agg = Invoke-Es 'POST' "$Pattern/_search" @{ size = 0; aggs = @{ m = @{ min = @{ field = '@timestamp' } } } }
        $winFrom = if ($agg.aggregations.m.value_as_string) { [DateTime]::Parse($agg.aggregations.m.value_as_string,
            [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal) } else { $winTo }
        $winFrom = $winFrom.AddMilliseconds(-$winFrom.Millisecond)   # whole second: the first doc is inside the window
    }
    if ($winTo -gt $winFrom.AddHours($MaxWindowHours)) { $winTo = $winFrom.AddHours($MaxWindowHours) }
    $fmt = "yyyy-MM-dd'T'HH:mm:ss.fff'Z'"
    $hb.window_from = $winFrom.ToString($fmt, [Globalization.CultureInfo]::InvariantCulture)
    $hb.window_to = $winTo.ToString($fmt, [Globalization.CultureInfo]::InvariantCulture)

    $lines = @{}; foreach ($v in $Vendors) { $lines[$v] = New-Object System.Collections.Generic.List[string] }
    if ($winTo -gt $winFrom) {
        $pit = (Invoke-Es 'POST' "$Pattern/_pit?keep_alive=2m" $null).id
        $after = $null
        do {
            $q = [ordered]@{
                size = $PageSize
                pit = @{ id = $pit; keep_alive = '2m' }
                sort = @(@{ '@timestamp' = @{ order = 'asc' } }, @{ '_shard_doc' = 'asc' })
                query = @{ range = @{ '@timestamp' = @{ gte = $hb.window_from; lt = $hb.window_to; format = 'strict_date_optional_time' } } }
                _source = @('@timestamp', 'hostIp', 'message', 'syslog_program', 'syslog_severity_code', 'syslog_facility_code')
            }
            if ($null -ne $after) { $q.search_after = $after }
            $res = Invoke-Es 'POST' '_search' $q
            if ($res.pit_id) { $pit = $res.pit_id }
            $hits = @($res.hits.hits)
            foreach ($h in $hits) {
                $v = Get-Vendor $h._source
                $lines[$v].Add((Format-Line $h._source $v))
            }
            if ($hits.Count) { $after = $hits[-1].sort }
        } while ($hits.Count -eq $PageSize)
    }

    foreach ($v in $Vendors) {
        $n = $lines[$v].Count
        $hb.fetched += $n
        if ($n) { $hb.by_vendor[$v] = $n }
    }
    if ($DryRun) {
        foreach ($v in $Vendors) {
            if ($lines[$v].Count) { "--- $v ($($lines[$v].Count))"; $lines[$v] | Select-Object -First $Preview }
        }
    } else {
        $day = $now.ToString('yyyyMMdd', [Globalization.CultureInfo]::InvariantCulture)
        foreach ($v in $Vendors) {
            if (-not $lines[$v].Count) { continue }
            $dir = Join-Path $OutDir $v
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
            [IO.File]::AppendAllText((Join-Path $dir "$v-$day.log"), (($lines[$v] -join "`n") + "`n"), $Utf8)
        }
        # checkpoint only after every line is on disk (a crash before this re-reads the window)
        if (-not (Test-Path -LiteralPath $StateDir)) { New-Item -ItemType Directory -Force -Path $StateDir | Out-Null }
        $tmp = "$StateFile.tmp"
        [IO.File]::WriteAllText($tmp, (@{ next_from = $hb.window_to } | ConvertTo-Json -Compress), $Utf8)
        Move-Item -LiteralPath $tmp -Destination $StateFile -Force
        # retention of the hand-off files (the UF has read them long before)
        if (Test-Path -LiteralPath $OutDir) {
            Get-ChildItem -LiteralPath $OutDir -Recurse -File -Filter '*.log' |
                Where-Object { $_.LastWriteTimeUtc -lt $now.AddDays(-$KeepDays) } | Remove-Item -Force
        }
    }
} catch {
    $hb.status = 'error'
    $hb.error = ($_.Exception.Message -replace '[\r\n]+', ' ')
} finally {
    if ($pit) { try { Invoke-Es 'DELETE' '_pit' @{ id = $pit } | Out-Null } catch { } }
}
$hb | ConvertTo-Json -Compress -Depth 4
