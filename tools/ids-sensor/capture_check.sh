#!/usr/bin/env bash
# READ-ONLY on the sensor: is the SPAN feed on cap0 arriving, and what is in it?
# usage: sudo bash capture_check.sh [packets]
N=${1:-1500}
S=$(mktemp)
ip -br link show cap0
r1=$(cat /sys/class/net/cap0/statistics/rx_packets); b1=$(cat /sys/class/net/cap0/statistics/rx_bytes)
sleep 10
r2=$(cat /sys/class/net/cap0/statistics/rx_packets); b2=$(cat /sys/class/net/cap0/statistics/rx_bytes)
echo "rate: $(( (r2 - r1) / 10 )) pps, $(( (b2 - b1) * 8 / 10 / 1000 )) kbit/s"
timeout 30 tcpdump -nn -e -i cap0 -c "$N" 2>/dev/null > "$S"
echo "sample: $(wc -l < "$S") frames, vlan-tagged: $(grep -c 'vlan ' "$S")"
echo "--- ethertypes"
grep -oE 'ethertype [A-Za-z0-9_-]+ \(0x[0-9a-f]+\)' "$S" | sort | uniq -c | sort -rn | head
echo "--- top IPv4 conversations (src > dst)"
grep 'IPv4' "$S" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)? > [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' |
  awk '{split($1,a,"."); split($3,b,"."); print a[1]"."a[2]"."a[3]"."a[4]" > "b[1]"."b[2]"."b[3]"."b[4]}' |
  sort | uniq -c | sort -rn | head -n 15
echo "--- subnets seen (/24, src or dst)"
grep 'IPv4' "$S" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk -F. '{print $1"."$2"."$3".0/24"}' | sort | uniq -c | sort -rn | head -n 20
echo "--- first frames"
head -n 6 "$S" | cut -c1-180
rm -f "$S"
echo "--- zeek"
tail -n 2 /data/zeek/logs/current/capture_loss.log 2>/dev/null
ls /data/zeek/logs/current/
echo "--- suricata capture counters"
tail -n 1 /data/suricata/eve.json 2>/dev/null | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); c=d.get("stats",{}).get("capture",{}); print({k:c[k] for k in c if k.startswith("kernel")}, "decoder.pkts=", d.get("stats",{}).get("decoder",{}).get("pkts"))' 2>/dev/null
