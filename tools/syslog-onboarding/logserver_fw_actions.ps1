# READ-ONLY: firewall messages stored by Scribbler since a UTC time, split by traffic action.
param([string]$Since = 'now-10m')
foreach ($ip in '10.4.20.254', '10.1.20.254') {
    foreach ($kind in @(@('accept/allow', 'message:(*accept* OR *allow*) AND message:*traffic*'),
                        @('deny/drop',    'message:(*deny* OR *drop* OR *block*) AND message:*traffic*'),
                        @('all',          '*'))) {
        $q = @{ size = 0; query = @{ bool = @{ filter = @(
                    @{ term = @{ hostIp = $ip } },
                    @{ range = @{ '@timestamp' = @{ gte = $Since } } },
                    @{ query_string = @{ query = $kind[1]; analyze_wildcard = $true } }) } } } | ConvertTo-Json -Depth 8
        $r = (Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body $q 'http://localhost:9200/scribbler*/_search').Content | ConvertFrom-Json
        "{0,-12} {1,-13} {2}" -f $ip, $kind[0], $r.hits.total.value
    }
}
