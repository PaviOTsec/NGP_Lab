#!/usr/bin/env bash
# M2-S2 staging on the kit's Kali VM (trainer runs it by hand, as root).
#   k1  start the read-only S7 poller (rogue reader)
#   k4  take the ET 200SP's IP: alias + gratuitous ARP every 50-70 s. Only after K3
#       (ET 200SP unplugged); refuses if anything still answers ARP for that IP.
# DRAFT, untested. Values are placeholders until M2S2-Q4. Needs iputils-arping
# (apt install iputils-arping; it conflicts with the 'arping' package).
set -euo pipefail

IFACE="${IFACE:-eth0}"
PLC_IP="${PLC_IP:-192.168.10.10}"          # drawing value, unconfirmed
ET200SP_IP="${ET200SP_IP:-192.168.10.11}"  # drawing value, unconfirmed
PREFIX="${PREFIX:-24}"
RACK="${RACK:-0}"
SLOT="${SLOT:-3}"
STATE_DIR=/run/m2s2
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$STATE_DIR"

case "${1:-}" in
  k1)
    nohup python3 "$HERE/s7_poll.py" "$PLC_IP" --rack "$RACK" --slot "$SLOT" \
      >>"$STATE_DIR/s7_poll.log" 2>&1 &
    echo $! >"$STATE_DIR/k1.pid"
    echo "K1 started (pid $(cat "$STATE_DIR/k1.pid")), log $STATE_DIR/s7_poll.log"
    ;;
  k4)
    # Duplicate-address detection: exit 0 means nobody answered, so the IP is free.
    if ! arping -D -c 3 -I "$IFACE" "$ET200SP_IP" >/dev/null; then
      echo "ABORT: $ET200SP_IP still answers ARP. Is the ET 200SP unplugged (K3)?" >&2
      exit 1
    fi
    ip addr add "$ET200SP_IP/$PREFIX" dev "$IFACE" label "$IFACE:k4"
    nohup bash -c "while true; do arping -U -c 1 -I '$IFACE' -s '$ET200SP_IP' '$ET200SP_IP' \
      >/dev/null 2>&1 || true; sleep \$((50 + RANDOM % 21)); done" >/dev/null 2>&1 &
    echo $! >"$STATE_DIR/k4.pid"
    ip -br addr show dev "$IFACE"
    echo "K4 staged: $ET200SP_IP on $IFACE (gratuitous ARP pid $(cat "$STATE_DIR/k4.pid"))"
    ;;
  *)
    echo "usage: $0 k1|k4" >&2
    exit 2
    ;;
esac
