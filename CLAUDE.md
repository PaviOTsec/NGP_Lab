# CLAUDE.md — Lab Console

Context and rules for working on this project. Read this before writing code.

## What this is

A lab management suite that runs on **MC01** (the management workstation of a workgroup
Hyper-V OT/ICS lab). Think "Ansible, customised for this lab, with a web console":

- **Console** — one-click access to every host and VM: terminals, file transfer, fan-out
  commands, Hyper-V power/checkpoint actions.
- **Playbooks** — declarative multi-step jobs over the inventory (e.g. "back up every network
  device", "training reset"), run from a web page, results and artifacts kept per run.
- **Shared clipboard** — a cl1p.net-style page every VM opens in a browser (or curls) to move
  text and files between machines without commands getting mangled across OSes.
- **Agent access (next)** — coding agents (Claude Code etc.) operate the VMs through the same
  API, under the operator's supervision.

It replaces a manual PowerShell-remoting workflow and a shelved `LabConnect.ps1` launcher
(kept in `docs/legacy/` for reference). The full requirements live in `docs/REQUIREMENTS.md`.
This file is the operational summary; when the two disagree, REQUIREMENTS.md wins and you
should flag the conflict.

## The environment (do not design against a different one)

- **MC01**: Windows 10/11 **client** OS (not Server). One interactive session at a time.
  Has internet. NIC1 on the management switch; NIC2 on the DMZ (10.1.20.0/24, **no default
  gateway**, static routes to lab subnets via 10.1.20.254). Python 3.13, Node installed.
- **Hypervisors** (observed 2026-10-09): DMZ-HOST-1 192.168.100.12, DMZ-HOST-2
  192.168.100.16, L4-HOST-1 192.168.100.11, and L2-HOST-1 192.168.100.13 (OT — **handle
  with care**, rule 13). There is no L3-HOST-1 (the drawing is wrong); HISTORIAN 192.168.30.10 is a
  stand-alone machine. MC01 has Hyper-V installed but runs no VMs (management console only). Windows Server 2022, **workgroup** (no domain), local
  accounts only. They run **Windows PowerShell 5.1**. `config/inventory.yaml` is the observed
  truth; the architecture drawing's IPs have drifted — never trust an address from it.
- **WinRM auth is NTLM** (no Kerberos). The console's client (pypsrp) does not consult
  Windows' `TrustedHosts`; that list only matters for native PowerShell remoting from MC01.
- **Hypervisor account** is `<HOST>\HyperVAdmin`: in Hyper-V Administrators + Remote
  Management Users. **Deliberately not a full admin.** A separate host-local Administrator
  credential exists for the rare host-level action.
- **Guests**: mix of Windows Server (some domain-joined to np.local), Ubuntu 22.04
  (SINEC INS, runs SSH), Kali, and vendor appliances (SINEMA RC, Scribbler, SINEC NMS).
- **Network devices**: SCALANCE, FortiGate, Palo Alto. **Allow-all during setup** (v1);
  tightened later (v2). Inventory section `network:`; reached over SSH.
- **L1 field devices** (PCS CPU 410 + ET 200SP, SIS CPU 410F, SAS IEDs + RTU, WAGO): inventory
  section `field:`, display-only (rule 13).

## Hard rules (these come from real time lost in this lab)

1. **Never widen HyperVAdmin.** Any action outside Hyper-V scope declares
   `credential: host-admin`; the pool then uses the host's separate `admin_credential` and
   errors if none is configured. It never silently uses a bigger account.
2. **`Set-VM` and friends fail silently.** Every state-changing Hyper-V call passes
   `-Passthru`, reads the resulting state back, and verifies it against what was asked. A
   call that returns no error is *not* proof it worked.
3. **`CheckpointType = Disabled` means "no preference", not "no checkpoints".** After any
   checkpoint, read the snapshot's actual `SnapshotType` with `Get-VMSnapshot` and report it.
   Offering a Production checkpoint requires healthy VSS in the guest — surface that first.
4. **`Get-Volume` is Access Denied under HyperVAdmin** (Storage WMI namespace). Use
   `Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'`. Likewise `Get-Service WinRM`
   fails ("Cannot find any service") — read `HKLM:\SYSTEM\CurrentControlSet\Services\WinRM`.
5. **Never touch vendor appliance images.** No agents, no SSH/WinRM install, no changing
   `fDisableCdm`. Appliances get power, checkpoint, and web-UI links only.
6. **Credentials are a plaintext YAML file the operator chooses in the app** (upload or a
   path on MC01; format `config/credentials.example.yaml`). Never commit one; don't write
   passwords into the audit log or error text. (Secret hardening is deliberately out of
   scope for now — don't re-introduce a vault without being asked.)
7. **Two listeners.** The console (full control) binds 127.0.0.1 by default and requires the
   per-launch token on every route + Host check. The clipboard server binds 0.0.0.0 so VMs
   can reach it and must expose **only** clipboard-board routes — never anything that
   touches a host.
8. **No runtime internet/CDN dependency.** Bundle all frontend assets and Python wheels. The
   clipboard page is a single ES5 file with no libraries (VMs may only have IE11/old Edge).
9. **PowerShell Direct does not work against Linux guests.** Never offer it for them.
10. **Windows PowerShell 5.1 `ConvertTo-Json` writes enums as integers** (`State: 2`). Cast
    every enum field to `[string]` on the host before serialising.
11. **Never translate line endings by accident.** Remote file I/O is binary (`write_bytes`/
    `read_bytes`); text conversion happens only in `app/core/textfmt.py`, only on request.
12. **Verify identity before sending any credential.** WinRM/SMB: the NTLM challenge names
    the host (`app/core/identity.py`) and must match the inventory `hostname`. SSH: the host
    key must match `ssh_fingerprint` when pinned. This applies to ad-hoc scripts too. (On
    2026-10-09 the drawing's "DMZ-HOST-2" address was really L2-HOST-1, and "L3-HOST-1" was
    an L2 bare-metal box; credentials were sent before this rule existed.)
13. **L2 and below: in scope, handle with care** (operator, 2026-10-21; replaces the old
    out-of-scope ban, its passphrase override and its per-device exceptions). L2-HOST-1, its
    PCS 7 guests (OSS01, ES01, OSC01/02), L2BM_BR, OT-FW, SW-L2, the WAM763-1 AP, the cell
    switches and the L1 field devices are in the inventory and on the dashboard. Care means:
    - **Rule 12 and rule 14 apply in full.** Identity/host-key pin before any credential;
      read-only unless the operator asked for the change.
    - **One device at a time, backup first.** Dated config backup before any change to an
      L2/L1 device; record + rollback in the relevant `tools/*/README.md`.
    - **No broad scans of L2/L1 subnets** (192.168.1–4.0/24, 192.168.20–21.0/24). Address only
      known devices, by name from the inventory.
    - **L1 controllers, IO, IEDs and the RTU are display-only** (inventory `field:`, kind
      `field`): never probed, never given a credential (the model rejects one), never written
      to, programmed, mode-changed or reset by the console or an agent. Engineering goes
      through ES01 / TIA / DIGSI by the operator. The SIS (192.168.2.0/24) gets extra caution.
    - **OT segments (L2, L1, Plantbus) are flagged `ot`:** the dashboard badges them, power
      actions need the target name typed, no checkpoint button (PCS 7 licences), and broad
      playbook selectors skip them unless the playbook names them, selects their segment or
      sets `include_ot: true`.
    - **Report every L2/L1 action** in the audit log and to the operator.
    Host-key pins for the OT network devices live in `config/inventory.yaml`; the OT-FW WBM TLS
    cert pin is in its comments. Earlier supervised work under the old exceptions (OT-FW
    SNMP/NTP, WAP Wi-Fi VLANs, switch syslog/NTP/SPAN) is recorded in the Status section.
14. **Observe-only unless told otherwise.** Against the live lab, run read-only queries
    (`Get-*`, `whoami`, pre-auth probes) unless the operator has asked for a change.

## Transport selection (speed is a feature)

The backend keeps a pool of **warm** sessions and reuses them. It never spawns a fresh
`powershell.exe` per action. **The direct link is always tried first** whenever the target
has an address (and its route isn't `via-host`); the Hyper-V link comes after:

- Hypervisor shell → WinRM (PSRP) as HyperVAdmin.
- Windows guest shell → WinRM direct, else PowerShell Direct on its hypervisor.
- Linux guest / network device shell → one persistent SSH connection, channels multiplexed.
- Bulk file copy → SMB (Windows) or SFTP (Linux); falls back to chunked PowerShell only when
  nothing faster is reachable.
- Power/checkpoint → WinRM to the hypervisor, Hyper-V cmdlets.

## Stack

Backend: Python 3.13 (>=3.12), FastAPI, `pypsrp` (WinRM/PSRP), `asyncssh` (SSH/SFTP),
`smbprotocol` (SMB), `pywinpty` (local PTY). Frontend: React + Vite + TypeScript, `xterm.js`
terminals over WebSocket. Theme is Ngee Ann Polytechnic navy/gold (colour only, no NP
branding).

## Layout

- `backend/app/core/` — `pool.py` (transport selection), `hyperv.py` (all Hyper-V
  PowerShell), `credentials.py`, `clipstore.py` + `textfmt.py` (shared clipboard),
  `vmtext.py` (type-into-VM, push/pull), `session.py`, `audit.py`, `probe.py`.
- `backend/app/transports/` — `Transport` interface + winrm / ssh / smb / psdirect, and
  `psfiles.py` (byte-exact file I/O over a PowerShell channel).
- `backend/app/playbooks/` — `model.py` (schema), `template.py`, `modules.py` (step-module
  registry + built-ins), `engine.py` (registry + background runner), `builtin/*.yaml`.
- `backend/app/routes/` — console API; `board.py` is mounted on both listeners.
- `backend/app/clip_page/index.html` — the VM-facing clipboard page.
- `playbooks/` — operator playbooks (YAML) and `playbooks/modules/*.py` custom step types.

## Conventions

- Routes, playbook modules and the engine never call a transport implementation directly —
  they go through the session pool, which hands back a connected transport for a target.
- New lab capabilities are **playbook step modules** (`@module("name")`), not new routes,
  unless they need their own UI.
- Every externally visible action is written to the append-only audit log
  (`app/core/audit.py`): time, target, action, transport, result, actor.
- All Hyper-V PowerShell is centralised in `app/core/hyperv.py` so the `-Passthru`/verify
  pattern is enforced in one place, not copy-pasted.
- Routes that start asyncio tasks must be `async def` (plain `def` routes run in a thread
  with no event loop).
- Type hints everywhere. Unit tests use mocked transports (`tests/mocks.py`); integration
  tests are guarded behind an env var and a real host in the inventory.
- Run tests: `cd backend; $env:LABCONSOLE_TESTING=1; .\.venv\Scripts\python -m pytest -q`.
- Imports of Windows-only libraries are lazy/guarded so the test suite imports anywhere.
- No git on MC01 yet; snapshot before large refactors.

## Status

- 2026-10-09: scaffold generated.
- 2026-10-09: KeePass removed (plaintext credentials chosen in the app); shared clipboard
  (board page + curl API) added; playbook engine replaced the actions engine. Unit tests and
  a live smoke test of both listeners pass on MC01 against unroutable test addresses.
- 2026-10-09: first contact with the real lab (read-only). Verified live: NTLM/WinRM to 3
  hypervisors and 6 guests, PowerShell Direct to 3 L4 guests, the identity probe, enum
  stringification, output formatting. Found and fixed: PowerShell Direct output came back
  as 'None' (remoting-decorated strings). Built `config/inventory.yaml` from observation.
- 2026-10-16: DMZH1_SIEM set up as Splunk deployment server + receiver (9997), index
  `wineventlog` on D:. Config source and UF installer tooling in `tools/splunk-uf/` (README).
  Never `Restart-Service Splunkd` — the ~30 s shutdown trips the SCM timeout and leaves it stopped.
  UF 10.6.0.5 on all 8 Windows guests with logins, all connected. FW-South (operator-approved):
  rules `L4L5-to-DMZ-L3-AnyPort` / `DMZ-L3-to-L4L5-AnyPort` fix App-ID `application-default`
  drops; L4 guests are now reached by direct WinRM/SMB (`route: via-host` removed). Verified
  live: SMB file transfer.
- 2026-10-16 (later): Windows events now XML; Sysmon 15.22 on all 9 Windows hosts (`tools/sysmon/`,
  index `sysmon`); Splunk_TA_windows, CIM, Sysmon TA, Security Essentials, ESCU installed, 50 ESCU
  detections enabled as tracked alerts. DMZH1_SIEM has `DisableRootAutoUpdate=1` (KV store fix).
- 2026-10-19: SW-DMZ/Ops/WAN/Ent send syslog to Scribbler on DMZH1_LogServer (10.1.20.13:514);
  backups `Backups/20261019-pre-syslog/`, tooling + record in `tools/syslog-onboarding/`. SW-Mgmt
  pending (no default gateway). Later (rule-13 override): SW-L2/PCS/SIS/SAS also delivering, after the
  operator had OT→DMZ opened broadly: FW-South rule `OT-to-DMZ-Allow` (192.168.1–4.0/24 + 20.0/24 →
  10.1.20.0/24, any service, commit 92) + route 192.168.4.0/24, and OT-FW `ip route 10.1.20.0/24 via
  192.168.20.253`. Backups/rollback: `Backups/20261019-ot-dmz-rule/`, `tools/syslog-onboarding/README.md`.
- 2026-10-19 (rule-13 override): all 9 SCALANCE switches have NTP → SINEC INS 10.1.20.21 (+08:00, `time ntp`);
  8 syncing, SW-Mgmt configured but unsynced (no gateway). `tools/syslog-onboarding/scalance_ntp.py`.
  FW-North, FW-South and OT-FW were already synced to 10.1.20.21 (NMS onboarding); checked read-only.
- 2026-10-19: FW-North, FW-South (commit 94) and OT-FW send syslog to Scribbler. Then "log only denied traffic":
  FW-South allow rules unlogged + `interzone-default` logged → Scribbler (commit 96); FW-North accept policies
  `logtraffic disable`, implicit-deny + local-in-deny logged. Backups `Backups/20261019-fw-syslog/`,
  `Backups/20261019-fw-logging/`; record in `tools/syslog-onboarding/README.md`.
- 2026-10-19 (later): network-device syslog in Splunk — UF on DMZH1_LogServer reads Scribbler's local ES
  read-only (`lab_scribbler_bridge`) → index `netdev`; Fortinet + PAN add-ons; 12 `LAB NET` alerts.
  Reconciled exactly vs Scribbler. Plan `docs/SPLUNK_SCRIBBLER_PLAN.md`, record `tools/splunk-uf/README.md`.
- 2026-10-19: SW-Ops port mirroring (SPAN) on: P0.1–P0.7 both directions → P0.8, session 1 active, left on.
  Backup `Backups/20261019-span/`. Guide tooling `tools/guidegen/` (boxed WBM screenshots → .docx);
  guide `Docs/guides/SCALANCE Port Mirroring (SPAN).docx`. Record + rollback in `tools/guidegen/README.md`.
- 2026-10-20 (rule-13 override): SPAN on all 8 switches except SW-Mgmt — every port both directions → last
  GbE port (SW-DMZ P16, others P8), session 1 Active; SW-Ops was already set. WAM763-1 AP has no mirroring.
  Backup `Backups/20261020-span/`, `tools/syslog-onboarding/scalance_span.py`, record + rollback in its README.
- 2026-10-20: lab mail. hMailServer 5.7.1 on L4H1_MailServer (domain `mail.np.local`, DNS A/MX on DC, 11
  accounts, lab subnets only, no relay), Thunderbird 153.5esr on L4H1_RAC (remoteIT preset for all users via
  mozilla.cfg), logs → Splunk index `mail` (`lab_hmailserver_inputs`, `lab_mail`). Welcome email sent to all
  mailboxes. 5.7 ignores `MaskPasswordsInLog` but masks always. Record + rollback: `tools/hmailserver/README.md`.
- 2026-10-20: IDS sensor L4H1_IDS (Ubuntu 24.04.5, 12 vCPU/32 GB, L4-HOST-1): mgmt0 WAN 10.5.20.60, cap0 for the
  SPAN aggregator (operator connects it). Suricata 8.0.7 + ET Open, Zeek 9.0.0 cluster + ICSNPP; UF → indexes
  `zeek`/`suricata` (Splunk_TA_zeek, CCX Suricata TA). Packages via temporary MC01 proxy (`mini_proxy.py`).
  Found: SIEM clock ~52 s slow (Hyper-V time sync, not NTP) — not changed. Record + rollback: `tools/ids-sensor/README.md`.
  2026-10-21: SPAN feed connected — L4-HOST-1 Embedded NIC 2 → external vSwitch `SPAN` → IDS `capture` (mirror
  Destination, trunk, external port MonitorMode=2). Feed so far looks DMZ-side only (no OT L2); operator to confirm.
  Suricata EXTERNAL_NET = public + 10.5.20.0/24 + 192.168.20.0/24 (operator), HOME_NET still all RFC1918.
  Splunk dashboard Lab Security > IDS Overview (`lab_ids_overview.xml`, lookup `lab_zones`, macros `ids_*`).
- 2026-10-21: no Splunk ES entitlement (licence = Enterprise only; Splunkbase 403 for ES) → DIY risk-based
  correlation in 6 steps (`tools/splunk-uf/README.md` "Correlation"). Step 1 done: `lab_assets` lookup generated
  from the inventory by `tools/splunk-uf/make_assets.py` (rerun after inventory changes).
- 2026-10-21 (rule-13 override): SINEMA RC device `Scalace_firewall` (OT-FW, VPN 172.30.0.2) exports L2/L1 to
  `vpn_device_group` (user `student`): 192.168.1–4.0/24 as-is, 192.168.20.0/24 as **172.17.20.0/24** (1:1 NAT —
  the tunnel itself originates from 192.168.20.254), "network gateway" off = source NAT on OT-FW. OT-FW config
  unchanged (`autofwnat`). End-to-end client test pending. Record + rollback: `tools/sinemarc-l2/README.md`.
- 2026-10-21: rule 13 changed from "L2 and below out of scope" to "in scope, handle with care"
  (operator). Inventory gained L2-HOST-1, L2H1_OSS01/ES01/OSC01/OSC02 (no vm_name/credential yet —
  fill from Get-VM and pin hostnames first), L2BM_BR, OT-FW, SW-L2, WAP-L2, SW-PCS/SIS/SAS and a
  `field:` section (8 L1 devices). New `L1` segment, `field` kind, `Target.ot`, selector `include_ot`.
  L2-HOST-1 gets a warm HyperVAdmin session on the next launch (first console login there).
- 2026-10-21 (later): read-only L2 discovery (`tools/l2-discovery/l2_discover.py`; identity check, then
  Get-VM/Get-VMNetworkAdapter as HyperVAdmin; NTLM name probes, no credentials). L2-HOST-1 runs ES01,
  OSC01, OSC02, OSS01, all domain-joined (NP), Running; the "unidentified" 192.168.20.13/.14 are the OSC
  Plantbus NICs; Terminalbus 192.168.21.x is not reachable from MC01; ES01 also holds 192.168.1.241.
  vm_name/hostname pins added; still no credentials on the PCS 7 VMs. New Inventory screen edits
  `inventory.yaml` as text (`app/core/inventory_edit.py`): validate → dated `.bak-` backup → write
  (line endings kept) → reload + re-warm; refuses if the file changed on disk; OT warnings in the confirm.
  Model now rejects an OT network device with a credential but no `ssh_fingerprint`.
- Still untested live: file transfer (SMB/SFTP), power/checkpoint actions, type-into-VM,
  host-admin (CoreAdmin) logins, switch SSH logins, playbook runs. Search `TODO(mc01)`.
- Next: agent access (MCP server + `labctl` CLI over the same API), network-device backup
  modules, native VMConnect/RDP launches (FR-12).
