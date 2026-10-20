# READ-ONLY: which source IPs Scribbler has stored in the last 2 hours, and the newest message from each.
$q = '{"size":0,"query":{"range":{"@timestamp":{"gte":"now-2h"}}},"aggs":{"h":{"terms":{"field":"hostIp","size":50},"aggs":{"last":{"top_hits":{"size":1,"sort":[{"@timestamp":"desc"}],"_source":["@timestamp","message","syslog_pri","ingest_protocol"]}}}}}}'
$r = (Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body $q 'http://localhost:9200/scribbler*/_search').Content | ConvertFrom-Json
foreach ($b in $r.aggregations.h.buckets) {
    $s = $b.last.hits.hits[0]._source
    "{0,-15} count={1,-5} last={2} pri={3} msg={4}" -f $b.key, $b.doc_count, $s.'@timestamp', $s.syslog_pri, ([string]$s.message).Substring(0, [Math]::Min(140, ([string]$s.message).Length))
}
if (-not $r.aggregations.h.buckets) { "no messages in the last 2h" }
