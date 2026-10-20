# Syslog onboarding of the SCALANCE switches (2026-10-19)

Target: **Scribbler Log Manager 1.15.35** (Syskey Softlabs) on DMZH1_LogServer 10.1.20.13 — web UI
https://10.1.20.13, Logstash input UDP 514 / TCP 1514, local Elasticsearch on 127.0.0.1:9200.
Scribbler has no device registry: a device "is onboarded" once its syslog arrives (the Devices
view is built from stored logs). No CLI/API step is needed on the Scribbler side.

Run with the backend venv: `.\backend\.venv\Scripts\python -I -X utf8 tools\syslog-onboarding\<script> ...`

| Script | What it does | Changes? |
|---|---|---|
| `scalance_syslog.py <backend> <out> apply\|remove <dev>...` | SCALANCE `events` → `syslogserver ipv4 10.1.20.13 514` + `client config syslog` (or the `no` forms); one device at a time, stops at first error, reads back `show events syslogserver` | **yes** (auto-saved) |
| `scalance_ntp.py <backend> <out> <dev>...` | SCALANCE NTP client → SINEC INS 10.1.20.21 (`ntp server id 1`, `ntp time diff +08:00`, `time ntp`); skips devices already syncing from it (peer in `show ntp info` + `Mode : NTP` in `show time`); one at a time, stops at first error | **yes** (auto-saved) |
| `scalance_span.py <backend> <out> <dev>...` | Port mirroring: Gi0/1..N-1 `both` → last GbE port Gi0/N (session 1, `monitor` on); refuses if Gi0/N is connected or session 1 exists differently; skips switches already set; one at a time, stops at first error, reads back `show monitor session 1` | **yes** (auto-saved) |
| `remote_ps_change.py <backend> <target> <ps1> <audit-action>` | State-changing PowerShell on an inventory target via the identity-checked pool, audited | **yes** |
| `logserver_fw_syslog.ps1` | Log server firewall rule `LabConsole-Syslog-UDP514` (UDP 514 in, remote = the 4 switch IPs), read back. Rollback: `Remove-NetFirewallRule -Name LabConsole-Syslog-UDP514` | **yes** |
| `logserver_seen.ps1` (via `tools/nms-onboarding/remote_ps.py`) | Source IPs stored by Scribbler in the last 2 h + newest message each | no |

## Record

- Backups first: `Backups/20261019-pre-syslog/<switch>/` — CLI (`versions`, `running-config all`,
  `running-config`) + WBM `Config` (.conf) and `ConfigPack` (.zip) for all 5 switches; `MANIFEST.json`,
  all checks passed. Transcripts of the changes in `transcripts/`.
- Before: syslog client off (`no client config syslog`), no server; event→syslog mappings and
  `severity syslog info` were already factory defaults (unchanged).
- Log server had no inbound rule for UDP 514 (default inbound = Block) — Scribbler had only ever
  stored 127.0.0.1. Added `LabConsole-Syslog-UDP514`. Trellix ENS Firewall is installed but its
  service (`mfefire`) is stopped; if ePO ever enables it, it will need the same exception.
- Applied + verified (messages stored in Scribbler): SW-DMZ 10.1.20.30 (pilot), SW-Ops 192.168.30.30,
  SW-WAN 10.5.20.30, SW-Ent 10.4.20.30. Path through FW-North/FW-South needed no change.
- **SW-Mgmt 192.168.100.30 not onboarded:** it has no default gateway (flat management network), so
  it cannot reach 10.1.20.13. Needs a routing decision by the operator.
- Not in scope: OT-FW (rule-13 exception covers SNMP/NTP only), WAP 192.168.20.30, firewalls.

### L2/L1 switches (rule-13 exception, operator 2026-10-19)
- Identity: first-contact SSH host keys (recorded in CLAUDE.md rule 13), banner `OpenSSH_9.0` like
  the other SCALANCE. Backups first: `Backups/20261019-L2-switches/` (CLI + WBM Config/ConfigPack,
  `MANIFEST.json`, all checks passed). Log-server rule extended to the 4 IPs.
- Applied + read back on SW-L2 192.168.20.50, SW-PCS 192.168.1.30, SW-SIS 192.168.2.30, SW-SAS 192.168.3.30.
- **Arriving: SW-L2 only.** L1 switches' gateway is the OT firewall (x.254), which has no route to
  10.1.20.0/24 (only `ip route 192.168.12.0/24 192.168.2.10`). MC01→L1 works only because FW-South
  source-NATs DMZ/L3→L2 to 192.168.20.189 (`Internal-Cross-Subnet-NAT`). Also FW-South allows
  Level2Zone→DMZ only from 192.168.20.0/24. Needed (operator decision, not done): OT-FW host route
  10.1.20.13/32 via 192.168.20.253 + FW-South rule 192.168.1.30/2.30/3.30 → 10.1.20.13 app syslog.
  Undo for L1 instead: `scalance_syslog.py ... remove SW-PCS=... SW-SIS=... SW-SAS=...`.

### OT → DMZ path opened (operator, 2026-10-19, rule-13 override; broad by operator choice)
- Backups first: `Backups/20261019-ot-dmz-rule/` — FW-South CLI text + XML export + on-box snapshot
  **`pre-ot-dmz-20261019.xml`** (identical to running), OT-FW CLI + WBM Config/ConfigPack; all checks passed.
- FW-South commit job 92 (`panos_ot_dmz.py`, dry run first): rule **`OT-to-DMZ-Allow`** Level2Zone →
  LevelDmzZone, src 192.168.1–4.0/24 + 192.168.20.0/24, dst 10.1.20.0/24, any app/service, log-end; no NAT
  (DMZ sees real OT IPs); route **`Return_to_Level1_Net4`** 192.168.4.0/24 via 192.168.20.254 (eth1/6).
  PAN-OS: in `set ... static-route` put `nexthop ip-address` last, or the command is rejected.
- OT-FW: `ip route 10.1.20.0 255.255.255.0 192.168.20.253` (it already routed L3/L4/L5 that way).
  OT-FW filtering remains shut down (routing only).
- Verified: SW-PCS/SIS/SAS syslog stored in Scribbler. All 8 switches except SW-Mgmt now deliver.
- Rollback: OT-FW `no ip route 10.1.20.0 255.255.255.0 192.168.20.253`; FW-South
  `delete rulebase security rules OT-to-DMZ-Allow` + `delete network virtual-router default routing-table
  ip static-route Return_to_Level1_Net4` + commit (or `load config from pre-ot-dmz-20261019.xml` + commit).

### NTP → SINEC INS (operator, 2026-10-19, rule-13 override, no backup by operator choice)
- SINEC INS 10.1.20.21 answers NTP (stratum 6). `show ntp server info` is the switch's *own* NTP server —
  the client is `show ntp info` (peer table) + `show time` (Mode/Last Sync).
- Already syncing (NMS onboarding, 2026-10-12; read-only check): SW-DMZ, SW-WAN, SW-Ent, SW-Ops. The first
  SW-DMZ run re-sent the identical sheet (detection bug, since fixed) — no effective change.
- Applied + syncing: SW-L2, SW-PCS, SW-SIS, SW-SAS (were `time manual`, clock at 01/2000, NTP disabled).
- **SW-Mgmt configured but not syncing** (stratum 0, Last Sync None): no default gateway, same as syslog.
- Transcripts: `Backups/20261019-ntp/transcripts/`. Undo per switch: `configure terminal` → `ntp` →
  `no ntp server id 1` → `exit` → `time manual` → `end` (CLI syntax of the undo not yet tested).
- Firewalls (read-only check via `tools/nms-onboarding/cli_help.py`, 2026-10-19 12:08): FW-North (`diagnose sys ntp
  status`: synchronized, 10.1.20.21 selected, stratum 6), FW-South (`show ntp`: synched to 10.1.20.21), OT-FW
  (peer 10.1.20.21, Mode NTP, last sync 12:08:09) — all already set by the NMS onboarding; no change made.

### Firewalls → syslog (operator, 2026-10-19)
- Backups first: `Backups/20261019-fw-syslog/` (FW-North config.txt + full-configuration; FW-South CLI + XML +
  on-box snapshot **`pre-syslog-20261019.xml`**; OT-FW CLI + WBM); all checks passed. Log-server rule extended
  with 10.4.20.254, 10.1.20.254, 192.168.1.254, 192.168.20.254 (OT-FW actually sends from **192.168.20.254**).
- FW-North (`fortigate_syslog.py`): `config log syslogd setting` → server 10.1.20.13, udp/514, facility local7,
  **source-ip 10.4.20.254** (otherwise it would send from transit 10.100.100.1). Rollback: `set status disable`.
- FW-South (`panos_syslog.py`, dry run first, commit job 94): syslog profile `Scribbler` (UDP 514, BSD), System +
  Config logs ("All Logs") → Scribbler, **service route syslog via ethernet1/4 10.1.20.254** (MGT port is down).
- OT-FW: `scalance_syslog.py` (server + client), then **event→syslog mappings**, which were all off on the
  SC646 (unlike the switches): cold-warmstart, linkchange, authentication-failure, power-change,
  faultstate-change, security-log, secure-ntp, config-change, service-information. `firewall-log` left off.
- Verified: all three firewalls' messages stored in Scribbler.

### Log only denied traffic (operator, 2026-10-19)
- Backups first: `Backups/20261019-fw-logging/` (FW-South snapshot **`pre-logging-20261019.xml`**); all checks passed.
- FW-South (`panos_log_deny.py`, dry run first, commit job 96): `log-start no` + `log-end no` on all 19 allow
  rules (read live; built-in default rules excluded — their names are reserved); log-forwarding profile
  `Scribbler-Deny` (traffic → syslog Scribbler); `interzone-default` override: deny, `log-end yes`,
  `log-setting Scribbler-Deny`. `intrazone-default` (allow) stays unlogged. Rollback: `load config from
  pre-logging-20261019.xml` + commit.
- FW-North (`fortigate_log_deny.py`): `logtraffic disable` on all 9 accept policies (policy 1 was `utm`, the rest
  `all`); `config log setting`: `fwpolicy-implicit-log enable`, `local-in-deny-unicast enable`, `local-out disable`.
  Long-lived sessions opened before the change keep their old flag and still send interim logs
  (`logid 0000000020`, e.g. NTP/SNMP flows up ~7 days) until they end or are cleared.
  Cleared 13:44–14:01 with `fortigate_clear_sessions.py ... none <proto> <policy>`: UDP on policies 4/5
  (NTP, SNMP), ICMP on 5, UDP on policy 0 (local/own traffic, incl. its syslog flow opened before
  `local-out disable`). TCP left alone. `filter duration` did NOT match old sessions on FortiOS 7.4 — don't
  rely on it. Verified: 0 accept-traffic messages from either firewall in Scribbler after 14:01:10.
- OT-FW: firewall function shut down, so no traffic logging either way; its accept iprules carry `log info` but are
  inactive and `firewall-log` is not mapped to syslog. Ruleset left untouched.
- `logserver_fw_actions.ps1` (read-only, via remote_ps.py): accept vs deny traffic messages per firewall in Scribbler.

### Port mirroring (SPAN) on all switches except SW-Mgmt (operator, 2026-10-20, rule-13 override for L2/L1)
- Backups first (CLI only, one switch per process — MC01 had ~1.5 GB commit free): `Backups/20261020-span/`
  (`versions`, `running-config all`, `running-config` × 8 switches, `MANIFEST.json`, all checks passed).
- Before: mirroring disabled + no session everywhere except SW-Ops (already P1–P7 → P8 since 2026-10-19, unchanged).
  Every destination port was `not connected` (SW-Ops P8 is connected = its capture device).
- Applied + read back (`Status : Active`): SW-WAN, SW-Ent, SW-L2, SW-PCS, SW-SIS, SW-SAS Gi0/1–7 both → **Gi0/8**;
  SW-DMZ (XC416-8) Gi0/1–15 both → **Gi0/16** (Ex0/17–24 SFP+ slots not present, not mirrored).
  Monitor barrier left at default (enabled). Transcripts: `Backups/20261020-span/transcripts/`.
- **WAM763-1 AP 192.168.20.30: not done — no mirroring feature** (FW V03.02: `monitor`/`mirror`/`port-mirror`
  are "Invalid Command" in config mode; checked with `?` only).
- CLI: `monitor session 1 destination interface gigabitethernet 0/N`, `monitor session 1 source interface
  gigabitethernet 0/i both`, `monitor`. Status: `show monitor`, `show monitor session 1`.
- Rollback per switch: `configure terminal` → `no monitor session 1` → `no monitor` → `end`.
