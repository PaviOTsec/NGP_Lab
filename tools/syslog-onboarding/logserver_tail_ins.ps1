# READ-ONLY: last 25 syslog messages Scribbler stored from SINEC INS 10.1.20.21 (last 45 min).
$q = '{"size":25,"sort":[{"@timestamp":{"order":"desc"}}],"query":{"bool":{"must":[{"term":{"hostIp":"10.1.20.21"}},{"range":{"@timestamp":{"gte":"now-45m"}}}]}},"_source":["@timestamp","message","syslog_pri","ingest_protocol"]}'
$r = (Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body $q 'http://localhost:9200/scribbler*/_search').Content | ConvertFrom-Json
"total=" + $r.hits.total.value
foreach ($h in $r.hits.hits) {
    $s = $h._source
    "{0}  pri={1}  proto={2}  {3}" -f $s.'@timestamp', $s.syslog_pri, $s.ingest_protocol, ([string]$s.message)
}
if (-not $r.hits.hits) { "no INS messages in the last 45m" }
