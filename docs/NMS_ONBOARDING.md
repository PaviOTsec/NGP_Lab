# SINEC NMS onboarding — decisions and status

Goal: make the in-scope network devices visible in SINEC NMS (V3.0, Control + Operation
`DMZH2Maint` on DMZH2_MaintServer 192.168.30.11), as groundwork for NMS *control*
(configuration management) later. Visibility-related settings only; no network changes.

## Devices

| Name | Address | Model / firmware | In NMS scope |
|---|---|---|---|
| SW-WAN | 10.5.20.30 | SCALANCE XC208G, V04.06.00 | yes |
| SW-Ent | 10.4.20.30 | SCALANCE XC208G, V04.06.00 | yes |
| SW-DMZ | 10.1.20.30 | SCALANCE XC416-8, XC400NG V01.04.01 | yes |
| SW-Ops | 192.168.30.30 | SCALANCE XC208G, V04.06.00 | yes (pilot) |
| FW-North | 10.4.20.254 | FortiGate-71G, FortiOS 7.4.11 | yes |
| FW-South | 10.1.20.254 | Palo Alto PA-440, PAN-OS 11.1.10-h1 | yes |
| OT-FW | 192.168.20.254 | SCALANCE SC646-2C, V03.00.02 | yes — rule-13 exception, SNMP only |
| SW-Mgmt | 192.168.100.30 | SCALANCE XC208G | **no** (operator) |
| 192.168.1/2/3.30 | — | SCALANCE | no (unreachable, L2 and below) |

## Decisions (operator)

| Date | Decision |
|---|---|
| 2026-10-12 | No Hyper-V checkpoints of lab VMs (voids licences). Use app/device-level backups. |
| 2026-10-12 | Visibility only; no VLAN/port/routing/IP/ruleset changes. Features (traps, control) added later. |
| 2026-10-12 | OT firewall SC646-2C is a one-off exception to CLAUDE.md rule 13: only what NMS needs. SSH enabled on it by the operator. |
| 2026-10-12 | SW-Mgmt is not onboarded. Switches 192.168.1/2/3.30 not onboarded. |
| 2026-10-12 | **SNMPv3 only** (authPriv, passwords, no certificates). Read *and* write access, because NMS control will be added later. |
| 2026-10-12 | FW-South (PAN-OS): add SNMP to the existing shared interface-management profile `Allow-Ping-Mgmt` (applies to ethernet1/3–1/6). |
| 2026-10-12 | FW-North (FortiOS): add `snmp` to port4's existing `allowaccess` list (keep ping https ssh http). |
| 2026-10-12 | Order: read-only work on all devices at once; changes one device at a time — pilot SW-Ops, then SW-WAN, SW-Ent, SW-DMZ, FW-North, FW-South, OT-FW. Backup verified before every change. |
| 2026-10-12 | Browser work runs headed (visible Edge on MC01); status report after every phase. |
| 2026-10-12 | Also point every device at NTP server **10.1.20.21** (SINEC INS) where possible. |
| 2026-10-12 | SNMPv3 = **SHA-256 + AES-128** on all devices; OT-FW **SHA-1 + AES-128** (its maximum), with its own credential in NMS. |
| 2026-10-12 | Disable (not delete) NMS scan ranges "Supervisory" (192.168.20.0/24) and "Control" (192.168.1.1–192.168.4.255). |
| 2026-10-12 | FW-South: add NTP service route via ethernet1/4. |
| 2026-10-12 | Timezone +08:00: SCALANCE `ntp time diff +08:00`; FW-North timezone US/Pacific → Singapore. |
| 2026-10-12 | `snmp agent version v3only` (drop v1/v2c `public`) per device, only after SNMPv3 is verified in NMS. |

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | Read-only discovery (devices, NMS, reachability) | done 2026-10-12 |
| 2 | Research exact commands + rollback; per-device command sheets | done 2026-10-12, reviewed |
| 3 | Backups of every device (and NMS's own backup) — no VM checkpoints | done 2026-10-12 |
| 4 | Pilot SW-Ops | done 2026-10-12 (SNMPv3 verified, `v3only` applied) |
| 5 | NMS: SNMPv3 credentials, scan ranges, discovery | done 2026-10-12 (folded into 4/6) |
| 6 | Roll out to remaining devices | done 2026-10-12 — all 7 on SNMPv3 + NTP |
| 7 | Codify as playbook modules | — |
| T | Topology (automatic where possible) | in progress — PA-440 LLDP done 2026-10-12 |

## Phase 1 findings (2026-10-12)

- All SCALANCE (incl. OT-FW): SNMP agent on, v1/v2c/v3 enabled, v1/v2c read-only with
  factory community `public`; only Siemens template SNMPv3 users; LLDP Tx/Rx on all ports;
  traps off. OT-FW firewall function is shut down (routing only).
- FortiGate: SNMP disabled, nothing configured. Shows "file system check recommended"
  (unsafe reboot) — `execute disk scan` reboots for up to an hour; operator's call.
- PA-440: no SNMP config; MGT port down (factory 192.168.1.1); managed via data
  interfaces with profile `Allow-Ping-Mgmt` (ping/https/ssh). LLDP disabled.
- NMS V3.0 (V03.00.00.00_06.00.00.15), single node, 0 monitored devices; Starter Set
  profile uses SNMP v2c. Existing scan ranges cover 1,788 addresses — **review before any
  scan** (must not include L2/L1 subnets).
- NMS host reaches all 7 devices (ping, 22, 443). UDP 162 on it is held by the Windows
  SNMP Trap service (relevant when traps are added).
- Raw outputs: `%LOCALAPPDATA%\LabConsole\nms-onboarding\20261012-phase1\` (not in repo).

## Phase 2 findings (2026-10-12)

Sources: each device's own CLI help (`?`, read in config mode without executing — one SSH
session per query, discarded on disconnect; verified afterwards that nothing was created),
Siemens *SCALANCE Layer 2 Switches CLI V4.4* (02/2023) and *SCALANCE SC-600 CLI V3.0*
(11/2022) manuals, PAN-OS 11.1 docs, FortiOS 7.4 CLI reference, SINEC NMS V3.0 UI.

### SNMPv3 algorithms actually offered

| Platform | Auth | Privacy |
|---|---|---|
| XC208G V4.6 (SW-WAN/Ent/Ops) | md5, sha, **sha256** | DES, AES128, AES256 |
| XC416-8 XC400NG V1.4 (SW-DMZ) | md5, sha, **sha256** | DES, AES128, AES256 |
| SC646-2C V3.0.2 (OT-FW) | md5, **sha** (SHA-1 only) | DES, **AES128** |
| FortiOS 7.4 (FW-North) | md5, sha, sha224, **sha256**, sha384, sha512 | aes (=AES-128), aes256, aes256cisco, des |
| PAN-OS 11.1 (FW-South) | SHA, SHA-224, **SHA-256**, SHA-384, SHA-512 | AES (=AES-128), AES-192, AES-256 |
| SINEC NMS V3.0 | MD5, SHA-1, **SHA-256** | **AES-128**, AES-192, AES-256, DES |

AES-128 is the only standardised SNMPv3 cipher (RFC 3826); AES-192/256 come in two
incompatible vendor variants, so AES-128 avoids interop failures. SHA-256 (RFC 7860) is
standard. The OT firewall cannot do SHA-256.

### Other facts that shape the commands
- SCALANCE: config is **auto-saved** (every command persists immediately); time mode is
  **Manual** (SW-Ops clock reads 01/13/2000); NTP client disabled. Passwords max 32 chars.
- FortiGate: `ntpsync enable` but no custom server (default FortiGuard, no internet);
  `server-mode enable` on `fortilink` (kept). Timezone **US/Pacific**.
- PA-440: timezone Singapore; **no service routes**, so NTP would leave via the MGT port,
  which is down — NTP needs a service route (`route service ntp source interface ethernet1/4`).
- NMS: Starter Set *Initial credentials* = one SNMP credential set per parameter profile,
  separate tabs for SNMP read (monitoring) and SNMP write (configuration); SSH/NETCONF/HTTPS
  credentials are a third tab. Automatic network scan is **off**. "Trust newly discovered
  devices" is on.
- **NMS scan ranges (DANGER):** 10.1.20.0/24 "DMZ", 192.168.30.0/24 "DMZ2",
  **192.168.20.0/24 "Supervisory"** and **192.168.1.1–192.168.4.255 "Control"** — all
  enabled. The last two are L2/L1 (rule 13). They must be disabled before any scan.
- NTP server 10.1.20.21 answers (stratum 6, local clock, ~11 s from MC01).
- MC01 timezone: Singapore (UTC+08:00).

## Command sheets (DRAFT — for operator review; nothing applied)

Placeholders: `<AUTH>` / `<PRIV>` = two random 24-char alphanumeric passwords, generated in
phase 4 and stored in the credentials file as `snmpv3/nms` (auth) and `snmpv3/nms-priv`
(priv). SNMP user name: `sinecnms`. NMS host: 192.168.30.11.

### SCALANCE XC208G / XC416-8 (SW-Ops pilot, then SW-WAN, SW-Ent, SW-DMZ)

```
configure terminal
snmp view NMSView 1 included
snmp user sinecnms auth sha256 <AUTH> priv AES128 <PRIV>
snmp group NMSGroup user sinecnms security-model v3
snmp access NMSGroup v3 priv read NMSView write NMSView notify NMSView
ntp
ntp server id 1 ipv4 10.1.20.21
ntp time diff +08:00
exit
time ntp
end
```
Verify: `show snmp user`, `show snmp group access`, `show ntp info`, `show time`
(Mode NTP, Last Sync set). Then NMS polls the device with SNMPv3.
Optional, only after NMS is confirmed on v3 (decision "SNMPv3 only"): `snmp agent version v3only`.

Rollback (reverse order):
```
configure terminal
time manual
ntp
no ntp server id 1        ! exact `no` form confirmed with ? before use
exit
no snmp access NMSGroup v3 priv
no snmp group NMSGroup user sinecnms security-model v3
no snmp user sinecnms
no snmp view NMSView 1
snmp agent version all    ! only if v3only was applied
end
```

### SCALANCE SC646-2C (OT-FW — rule-13 exception, last)
Same as above except `snmp user sinecnms auth sha <AUTH> priv AES128 <PRIV>` (SHA-1: the
firmware's maximum). No firewall/ruleset/interface commands.

### FortiGate-71G (FW-North)
```
config system snmp sysinfo
    set status enable
end
config system snmp user
    edit "sinecnms"
        set queries enable
        set security-level auth-priv
        set auth-proto sha256
        set auth-pwd <AUTH>
        set priv-proto aes
        set priv-pwd <PRIV>
    next
end
config system interface
    edit "port4"
        set allowaccess ping https ssh http snmp
    next
end
config system global
    set timezone "Asia/Singapore"     ! exact name/index confirmed with ? before use
end
config system ntp
    set ntpsync enable
    set type custom
    config ntpserver
        edit 1
            set server "10.1.20.21"
        next
    end
end
```
Verify: `get system snmp sysinfo`, `show system snmp user`, `diagnose sys ntp status`.
FortiGate SNMP is read-only by design (no SNMP write).
Rollback: `config system interface / edit port4 / set allowaccess ping https ssh http`;
`config system snmp user / delete "sinecnms"`; `config system snmp sysinfo / set status disable`;
`config system ntp / config ntpserver / delete 1 / end / set type fortiguard`.

### Palo Alto PA-440 (FW-South)
```
configure
set deviceconfig system snmp-setting access-setting version v3 views NMSView view all oid 1.3.6.1 option include mask 0xf0
set deviceconfig system snmp-setting access-setting version v3 users sinecnms view NMSView authproto SHA-256 authpwd <AUTH> privproto AES privpwd <PRIV>
set network profiles interface-management-profile Allow-Ping-Mgmt snmp yes
set deviceconfig system ntp-servers primary-ntp-server ntp-server-address 10.1.20.21
set deviceconfig system ntp-servers primary-ntp-server authentication-type none
set deviceconfig system route service ntp source interface ethernet1/4
commit description "SINEC NMS onboarding: SNMPv3 + NTP"
```
Before commit: `show config diff` reviewed. `Allow-Ping-Mgmt` is on ethernet1/3–1/6, so
SNMP opens on all four (operator decision). PAN SNMP is read-only by design.
Verify: `show ntp`, `show system state | match snmp`, NMS poll.
Rollback: `delete` the same nodes (`... users sinecnms`, `... views NMSView`,
`... ntp-servers`, `... route service ntp`), `set network profiles
interface-management-profile Allow-Ping-Mgmt snmp no`, commit — or revert to the pre-change
saved snapshot from phase 3 (`load config from <snapshot>` + commit).

### SINEC NMS (phase 5, in the visible browser)
1. **Disable** scan ranges "Supervisory" (192.168.20.0/24) and "Control"
   (192.168.1.1–192.168.4.255) — before anything else.
2. Starter Set → Initial credentials → SNMP monitoring: Version 3, AuthPriv, SHA-256,
   AES-128, user `sinecnms`, `<AUTH>`/`<PRIV>`; SNMP configuration (write) tab: same.
3. Add the devices (scan of the enabled ranges or add by IP), confirm each appears.
4. OT-FW (SHA-1): needs a per-device credential override, or a second set — verified in phase 5.

## Phase 3 — backups (2026-10-12, ~09:52–09:59 SGT)

Location (MC01, not in repo): `%LOCALAPPDATA%\LabConsole\nms-onboarding\20261012-phase3-backup\<device>\`
File naming: `<device>_<ip>_<yyyyMMdd-HHmmss>_<content>` (e.g.
`SW-Ops_192.168.30.30_20261012-095244_running-config-all.txt`). `MANIFEST.json` holds the
SHA-256 of every file. All checks passed: non-empty, complete (ends as the platform's config
ends), the device's own IP inside every config, zips valid. `.raw` = unprocessed terminal capture.
No VM checkpoints were taken.

| Device | CLI text | Native / restorable format |
|---|---|---|
| SCALANCE ×5 (incl. OT-FW) | `versions`, `running-config-all` (incl. defaults), `running-config` | WBM Load&Save → `Config` (.conf) and `ConfigPack` (.zip: config + users + certificates) |
| FW-North | `system-status`, `full-configuration` | `config.txt` = FortiOS backup format (`#config-version` header) |
| FW-South | `system-info`, `running-config-cli-text` | XML API export `api_running-config.xml` (byte-exact) + on-box snapshot **`nms-pre-onboarding-20261012.xml`** (identical hash) ; `check pending-changes` = no |
| SINEC NMS | — | Built-in daily system backup 12:01 → `C:\Siemens\SINECNMS_BACKUP\` on MaintServer (2 kept; latest 2026-10-11, 102 MB, Control+Operation). NMS unchanged since. |

Restore paths: SCALANCE — WBM Load&Save → `Load` the `.conf`/`ConfigPack` (or paste CLI);
FortiGate — System → Configuration → Restore with `config.txt`; PAN — `load config from
nms-pre-onboarding-20261012.xml` + commit (or import the XML); NMS — Siemens restore procedure
from the system backup zip.

## Phase 4 — pilot SW-Ops + NMS baseline (2026-10-12)

Device (SW-Ops 192.168.30.30), applied over SSH, transcript (secrets masked) in
`%LOCALAPPDATA%\LabConsole\nms-onboarding\20261012-phase4\`:
- SNMPv3 user `sinecnms` (SHA-256/AES-128), group `NMSGroup` (read/write/notify `NMSView`),
  view `NMSView` = OID 1. **Order matters on SCALANCE: user → group → access → view** (view
  is refused until its access entry exists). `show snmp user` displays auth as "DES_CBC" —
  firmware display bug; running-config shows `auth sha256`.
- NTP 10.1.20.21, `ntp time diff +08:00`, `time ntp` → clock moved 2000-01-14 → 2026-10-12
  10:17 SGT, last sync via NTP. Auto-save committed.
- Verified: SNMPv3 GET from MC01 with the credentials works; wrong auth password is rejected
  ("Wrong SNMP PDU digest").

SINEC NMS (Control + Operation DMZH2Maint):
- Starter Set → Initial credentials, SNMP monitoring **and** configuration tabs: v3, AuthPriv,
  SHA-256, AES-128, user `sinecnms` (Operation confirms the same after sync).
- Starter Set → Discovery settings: **"Discovery of NAT / routers" OFF** (it followed routers
  into L1/L2).
- Starter Set → SIMATIC monitoring settings: **all four options OFF** (NMS would otherwise log
  onto SIMATIC CPUs, and pull in IO devices outside the scan ranges).
- Operations → Edit discovery restriction list: `L1L2_noPROFINET` = 192.168.1.0–192.168.4.255,
  192.168.20.0/24, "No PROFINET discovery", enabled (names: no spaces).
- Scan ranges: overlapping ranges are not allowed (even disabled ones), and a range's name is
  read-only when edited. **DMZ2 was narrowed from 192.168.30.1–255 to 192.168.30.30–30**
  (enabled); DMZ (10.1.20.1–255), Supervisory (192.168.20.1–255), Control (192.168.1.1–
  192.168.4.255) remain disabled. Policy: single-device ranges only.
- Gated scan (only expected range enabled, Operation synced) → job 1012, ~1.5 min → SW-Ops
  discovered as SCALANCE XC208 PN G, status OK, trusted. Device list = SW-Ops + the NMS
  management station only.

Incident (same day, ~10:20–10:55): an unintended "Start network scan" click (it starts
immediately, no dialog) ran over DMZ + DMZ2 with NAT/router discovery on; NMS followed routers
and listed/monitored L1/L2 devices including two CPU410E F PLCs (read-only polling). Scan was
stopped, all discovered devices removed by the operator, settings above applied to prevent
recurrence.

### Phase 4 addendum — `v3only` on SW-Ops (2026-10-12 11:27–11:50)
- First two attempts: NMS kept polling with v1/v2c (≈12 refused/min, "Bad SNMP Version
  errors"; NMS: "device is no longer reachable with SNMP") → rolled back to `all` each time.
- Root causes in NMS (both needed fixing):
  1. Starter Set → **SNMP settings for discovery** had "SNMP Settings V1" (v1) and
     "SNMP Settings V2" (2c) enabled. NMS requires ≥1 enabled entry, so an SNMPv3 entry
     `SNMPv3_sinecnms` (AuthPriv, SHA-256, AES-128) was created and V1/V2 disabled.
  2. The device's own entry in the Operation's **Device credential repository** keeps the
     credentials it was first discovered with (here v2c, 11:13) and overrides the initial
     credentials. Fixed via Edit → "Restore initial credentials" per tab (monitoring and
     configuration) → both v3 → Save.
- Third attempt: 625 SNMP requests in 3 min, 0 refused; NMS status OK. `v3only` kept.
- For the rollout: new devices are discovered with the v3 entry; still check each device's
  credential-repository entry (both tabs = v3) before applying `v3only`.
- Side finding: NMS SSH/HTTPS initial credentials (`admin` + stored password) fail SSH auth
  on the switches ("Authentication failed") — only matters for NMS control later.

## Phase 6 — rollout (2026-10-12 11:55–13:45)

| Device | SNMPv3 | NTP / time | NMS (type, status) | v1/v2c off |
|---|---|---|---|---|
| SW-Ops 192.168.30.30 | sinecnms SHA-256/AES-128 | synced, +08:00 | SCALANCE XC208 PN G, OK | `v3only` |
| SW-WAN 10.5.20.30 | same | synced | XC208 PN G, *maintenance demanded* (MRP ring open, see below) | `v3only` |
| SW-Ent 10.4.20.30 | same | synced | XC208 PN G, *maintenance demanded* (MRP) | `v3only` |
| SW-DMZ 10.1.20.30 | same | synced | XC416-8, OK | `v3only` |
| FW-North 10.4.20.254 | sha256/aes; agent on; `snmp` added to port4 allowaccess | ntp custom 10.1.20.21, synced; tz Asia/Singapore | DEFAULT_SNMP_Device (FortiGate-71G), OK | n/a (no communities) |
| FW-South 10.1.20.254 | SHA-256/AES; `snmp yes` on Allow-Ping-Mgmt; commit job 84 | 10.1.20.21 + service route ethernet1/4 src 10.1.20.254/24, synced | DEFAULT_SNMP_Device (PA-440), OK | n/a |
| OT-FW 192.168.20.254 | sinecnms **SHA-1**/AES-128 | synced, +08:00 | SCALANCE SC646 (2GS00-2AC2), OK | `v3only` |

NMS scan ranges (all single IP, enabled): DMZ2=192.168.30.30, SWWAN, SWEnt, DMZ=10.1.20.30,
FWNorth, FWSouth, Supervisory=192.168.20.254. "Control" (192.168.1.1–4.255) stays disabled.
SNMP settings for discovery: `SNMPv3_sinecnms` (SHA-256) + `SNMPv3_sha1` (SHA-1, for OT-FW);
V1/V2 disabled. Operation: automatic device type change enabled.

Lessons:
- PAN-OS NTP service route needs `source interface … address …`; a failed commit leaves the
  candidate dirty — always `revert config` (script now does).
- FortiOS `show` on SNMP user omits defaults (`priv-proto aes`, `queries enable`).
- NMS does not re-discover known devices; an existing ICMP-only device is fixed via Operation →
  Devices → advanced toolbar → **Change device type** (profile SCALANCE_SC6XX → SC646
  (2GS00-2AC2)) with SNMP settings `SNMPv3_sha1`.
- SW-WAN/SW-Ent "maintenance demanded": factory MRP (ring redundancy, Auto-Manager on Gi0/1–2)
  with no ring cabled. Fix would be `no ring-redundancy` — an L2 change, left to the operator.

## Topology (2026-10-12, from 14:20)

Goal (operator): NMS should draw the topology itself, with as little hand-drawing as possible.

**How NMS learns a link:** it reads the LLDP neighbour table (LLDP-MIB) of a monitored device over
SNMP. Verified by SNMPv3 walk: the SCALANCE switches publish it; **PA-440 and FortiGate do not**
(`lldpRemTable` empty on both, even with live neighbours). So a link is automatic only if a
SCALANCE is on one end and the other end *sends* LLDP and is itself a monitored NMS device.

Cabling found (read-only LLDP/MAC/ARP, `nms_phase1.py … topo`, raw in `20261012-topology\`):

| Link | Evidence | Automatic? |
|---|---|---|
| FW-North port4 ↔ SW-Ent Gi0/1 | LLDP (FortiGate sends per interface) | yes |
| FW-North port5 ↔ SW-WAN Gi0/1 | LLDP | yes |
| FW-South eth1/4 ↔ SW-DMZ Gi0/1 | LLDP since PA change below | yes |
| FW-South eth1/3 ↔ SW-Ops Gi0/3 | LLDP since PA change below | yes |
| FW-North port2 ↔ FW-South eth1/5 (transit 10.100.100.0/30) | ARP both sides | **never** (neither FW publishes LLDP-MIB) |
| FW-South eth1/6 → L2 switch 192.168.20.50 → OT-FW Gi0/1 | ARP + OT-FW LLDP | no (L2, rule 13) |
| OT-FW Gi0/2,3,5,6 → level1switch1/2/3 | OT-FW LLDP | no (L1, rule 13) |
| SW-Ops Gi0/1 ↔ HISTORIAN | LLDP (Broadcom NIC firmware) | possible once Historian is a monitored (ping) device |
| SW-DMZ Gi0/5 ↔ MC01 (USB NIC 00:e0:4c:4a:37:40) | LLDP (Windows 10 ms_lldp) | possible once MC01 is monitored |
| SW-DMZ Gi0/2 → DMZ-HOST-1 VMs; Gi0/3 → DMZ-HOST-2 VMs; Gi0/4 → SSM | MAC table | no — VMs/appliance send no LLDP |
| SW-Ent Gi0/2 → L4-HOST-1 VMs; SW-WAN Gi0/2 → (likely) L4-HOST-1 WAN | MAC table / link only | no |
| SW-Ops Gi0/2 → DMZ-HOST-2 (MaintServer/NMS) | by elimination | no |

Windows facts: Server 2022 guests have the `ms_lldp` driver bound but no `NetLldpAgent`
cmdlets (they come with the Data-Center-Bridging feature); MC01 (Win10) has them and does send.
Whether a Hyper-V vSwitch passes a VM's LLDP to the physical port is untested.

**PA-440 LLDP (operator-approved, commit job 86, 14:38):** backup first (`pan_export.py`,
running-config 21711 B, no pending changes); dry run, then commit via `nms_apply_panos_lldp.py`.
Diff: only `network lldp enable yes`, profile `NMS-LLDP` (tx-rx; sys-name/desc, port-desc, caps,
mgmt-address 10.1.20.254), and `lldp enable yes profile NMS-LLDP` on ethernet1/3 + 1/4 (the
only removals were those two `enable no` flags). eth1/5 and eth1/6 left off. Verified: PA sees
SW-Ops (port 3) and SW-DMZ (port 1); SW-DMZ and SW-Ops list "PA-440"; SW-DMZ's LLDP-MIB
reports the PA's management address 10.1.20.254 (what NMS matches on); routing unaffected.
NMS topology view not yet re-checked (MC01 ran out of RAM for the browser).

Note: the SCALANCE switches report sysName "sysName Not Set" — setting a system name is a
visibility-only option for nicer NMS labels (not done; operator's call).