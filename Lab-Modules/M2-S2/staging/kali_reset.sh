#!/usr/bin/env bash
# M2-S2 reset on the kit's Kali VM: stop K4 (alias + ARP loop) and K1 (poller).
# Run BEFORE reconnecting the ET 200SP, or its IP will clash with the alias (tracker G12).
# DRAFT, untested.
set -uo pipefail

IFACE="${IFACE:-eth0}"
ET200SP_IP="${ET200SP_IP:-192.168.10.11}"
PREFIX="${PREFIX:-24}"
STATE_DIR=/run/m2s2

for k in k4 k1; do
  if [[ -f "$STATE_DIR/$k.pid" ]]; then
    kill "$(cat "$STATE_DIR/$k.pid")" 2>/dev/null && echo "$k stopped"
    rm -f "$STATE_DIR/$k.pid"
  fi
done

ip addr del "$ET200SP_IP/$PREFIX" dev "$IFACE" 2>/dev/null && echo "alias $ET200SP_IP removed"

# Read back: the alias must be gone.
if ip -br addr show dev "$IFACE" | grep -qw "$ET200SP_IP"; then
  echo "FAIL: $ET200SP_IP is still on $IFACE" >&2
  exit 1
fi
echo "PASS: Kali clean. Now power off the Kali VM, then reconnect the ET 200SP."
