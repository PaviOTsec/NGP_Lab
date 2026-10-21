#!/usr/bin/env bash
# IDS smoke test, run from Kali (L4H1_Attacker_Kali 10.5.20.50) as the normal user - no sudo.
# Harmless traffic that Zeek logs and ET Open flags: a light service scan + scanner user-agents.
# Nothing is exploited. usage: bash ids_smoke_test.sh [target]
T=${1:-10.1.20.15}
echo "start $(date -u +%FT%TZ) target $T from $(hostname -I)"
ping -c 2 -W 2 "$T" >/dev/null && echo "ping ok" || echo "ping failed (may be filtered)"
echo "--- nmap service scan (top 100 TCP ports, connect scan)"
nmap -Pn -sT -sV --top-ports 100 -T4 --open "$T" | grep -E '^[0-9]+/tcp|Nmap done'
echo "--- nmap NSE http-title on 8000 (Nmap Scripting Engine user-agent)"
nmap -Pn -sT -p 8000 --script http-title "$T" | grep -E 'http-title|Nmap done'
echo "--- scanner user-agents"
for ua in "Mozilla/5.00 (Nikto/2.5.0) (Evasions:None) (Test:000001)" "sqlmap/1.8 (https://sqlmap.org)" "masscan/1.3 (https://github.com/robertdavidgraham/masscan)"; do
  printf '%-14s HTTP %s\n' "${ua%% *}" "$(curl -s -o /dev/null -m 5 -w '%{http_code}' -A "$ua" "http://$T:8000/en-US/account/login?return_to=%2Fetc%2Fpasswd")"
done
echo "--- directory-traversal style request"
printf 'traversal      HTTP %s\n' "$(curl -s -o /dev/null -m 5 -w '%{http_code}' --path-as-is "http://$T:8000/../../../../etc/passwd")"
echo "end $(date -u +%FT%TZ)"
