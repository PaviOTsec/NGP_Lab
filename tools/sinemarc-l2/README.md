# SINEMA RC: VPN access to L2 and below via the OT firewall (2026-10-21)

Operator request, under the rule-13 override (CLAUDE.md): the SINEMA RC user `student` must reach the
L2 and L1 networks **only through the VPN**. Later, clients will reach nothing but SINEMA RC 10.1.20.16,
and the OT firewall's packet filter will be switched on.

## How the path works
Student PC → SINEMA RC 10.1.20.16 (TCP 443 login, UDP 1194 tunnel, TCP 5443 fallback) → the firewall's
permanent tunnel (OT-FW SC646-2C 192.168.20.254, SINEMA device `Scalace_firewall`, id 2, VPN 172.30.0.2)
→ L2/L1. Neither the student PC's gateway nor the OT devices' gateways are involved.

## What was changed (only SINEMA RC; OT-FW config untouched)
Remote connections → Devices → `Scalace_firewall` → Network Settings:

| Setting | Before | After |
|---|---|---|
| Device is a network gateway | on | **off**, so SINEMA RC forces source NAT on OT-FW |
| L2_Plant | – | 192.168.20.0/24, **1:1 NAT → 172.17.20.0/24** |
| L1_PCS / L1_SIS / L1_SAS / L1_Net4 | – | 192.168.1/2/3/4.0/24, no NAT |
| Participant group (each subnet) | – | `vpn_device_group` (student is a member) |
| Port groups | – | none: full IP access (operator) |

192.168.12.0/24 (routed by OT-FW via 192.168.2.10) is left out (operator).

Why:
- **Source NAT** makes L1/L2 nodes see the firewall's own interface address, so they reply to it
  directly, whatever their gateway is. The L2 hosts use FW-South (192.168.20.253) as their gateway.
  Side effect: devices and logs see OT-FW, not the student's VPN IP.
- **1:1 NAT on 192.168.20.0/24**: OT-FW's tunnel starts from 192.168.20.254. Exporting that subnet
  without NAT would make the server route the tunnel's own packets into the tunnel. Students reach
  L2 hosts at 172.17.20.x, keeping the same host part (SW-L2 192.168.20.50 → 172.17.20.50).
- OT-FW has `autofwnat` on: it builds the firewall and NAT rules from the server's settings itself.
  Saving made the server drop and redial the device tunnel; it was back within the minute. OT-FW
  Information → SINEMA RC now lists all five subnets (`192.168.20.0/24 translated to 172.17.20.0/24`).

## When the lab is tightened later
- Keep OT-FW 192.168.20.254 → 10.1.20.16 UDP 1194 / TCP 443 / TCP 5443 open. Today FW-South's broad
  `OT-to-DMZ-Allow` rule covers it.
- Allow clients → 10.1.20.16 on the same ports.
- When OT-FW filtering is switched on, check that auto rules appear for the vlan2 subnets
  (192.168.2.0/24, 192.168.4.0/24) too. Keep the `sinemarcall` predefined HTTPS/SSH/ping (student WBM
  access to 172.30.0.2), and drop the any→any iprule.

## Scripts
- `src_wbm.py`: read-only SINEMA RC WBM in the visible Edge (CDP :9222). The TLS cert is checked
  against the fingerprint OT-FW pins for the server before login. Actions: `login`, `links`,
  `goto <path>`, `click <menu text>`, `html`.
- `src_device_subnets.py stage|save|remove`: prechecks the recorded state, fills the form with the
  page's own `loadNetworkSettingsData`, compares the form with the target, then saves and re-reads
  what the server stored. Writes to the audit log.

## Rollback
`python -I -X utf8 tools\sinemarc-l2\src_device_subnets.py backend <out> remove` restores "no
subnets, gateway on". Alternatively, in the GUI: delete the five subnets, tick the gateway box and
Save. The device tunnel redials by itself. Before/after screenshots and the OT-FW CLI backup are in
`Backups/20261021-sinemarc-l2/`.

## Not done / open
- End-to-end test from a student client: see the operator test steps below.
- SINEMA RC has no backup copies. A full server backup needs a backup coding password first.
- Device type on the server is "S615 / M804PB / M826 / M816" although the device is an SC646-2C.
  Subnets work; changing the type needs a new device password/certificate, so it was left alone.

## Operator test (student client)
1. Disconnect and reconnect in the SINEMA RC Client. The device should list the five subnets.
2. `tracert -d 192.168.1.30`: the first hop must be a 172.30.x address (VPN), not the LAN gateway.
3. Open https://192.168.1.30 (SW-PCS) and https://172.17.20.50 (SW-L2) one at a time. 172.17.20.x
   can only work through the VPN.
