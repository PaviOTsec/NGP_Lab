# SINEC NMS onboarding scripts (2026-10-12)

Working scripts from the SINEC NMS onboarding of the lab's network devices. The full record
(decisions, per-phase results, lessons) is in [`docs/NMS_ONBOARDING.md`](../../docs/NMS_ONBOARDING.md).
These are operator tools, not part of the Lab Console yet — phase 7 turns the useful parts
into playbook step modules.

**Conventions all scripts follow**
- Run with the backend venv and `-I`: `.\backend\.venv\Scripts\python -I -X utf8 tools\nms-onboarding\<script> ...`
  (most take the backend dir as the first argument and import `app.*` from it).
- Credentials come from `config/credentials.example.yaml` via the app's `CredentialStore`
  (`network/admin`, `snmpv3/nms`, `snmpv3/nms-priv`, `sinec-nms/web-portal`). Nothing is hardcoded;
  passwords are masked in transcripts and never printed.
- SSH host keys are pinned on the **authenticating** connection (`known_hosts=([key], [], [])`);
  TLS certs are checked against recorded pins before any web login.
- Outputs go to `%LOCALAPPDATA%\LabConsole\nms-onboarding\<date>-<phase>\`, named
  `<device>_<ip>_<yyyyMMdd-HHmmss>_<content>`.
- Browser scripts drive the **operator-visible** Edge over CDP. Start it first:
  ```powershell
  Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList `
    "--remote-debugging-port=9222","--remote-debugging-address=127.0.0.1", `
    "--user-data-dir=`"$env:LOCALAPPDATA\LabConsole\nms-browser-profile`"","--ignore-certificate-errors","--no-first-run"
  ```
  Close other heavy apps if MC01 is short of RAM — the Playwright driver dies at <1 GB free.

## Devices (SSH)

| Script | What it does | Changes? |
|---|---|---|
| `nms_phase1.py` | Read-only discovery: show/get commands on all NMS-tagged devices + reachability from the NMS host; mode `topo` = LLDP neighbours, MAC/ARP tables, interfaces | no |
| `cli_help.py` | Run show commands, or read `?` help in config mode without executing (one session per query, discarded on disconnect). PowerShell 5.1 drops `""` args — omit the query instead | no |
| `nms_backup.py` | CLI config backups (SCALANCE `running-config all`, FortiOS `show`/`full-configuration`, PAN text + on-box snapshot) with completeness checks + manifest | PAN: `save config to` snapshot only |
| `pan_export.py` | PAN-OS byte-exact XML export (running + named snapshot) via XML API keygen; `check pending-changes` | no |
| `wbm_backup.py` | SCALANCE WBM Load&Save → presses **only** `Save` on rows Config / ConfigPack (visible browser) | no |
| `verify_backups.py` | Non-empty, device IP inside, zips valid; writes `MANIFEST.json` | no |
| `add_snmp_creds.py` | Generates the two SNMPv3 passwords into the credentials file (not printed) | credentials file |
| `nms_apply_scalance.py` | SCALANCE: SNMPv3 user/group/access/view (**order matters: view last**) + NTP + `time ntp`; stops at first error | **yes** |
| `nms_apply_cmds.py` | Generic SCALANCE command list (`;;`-separated), e.g. `snmp agent version v3only` / `all` | **yes** |
| `nms_apply_fortigate.py` | FW-North: SNMPv3 user, agent on, `snmp` added to port4 allowaccess (pre-checked), NTP, timezone; `abort` on error | **yes** |
| `nms_apply_panos.py` | FW-South: set → diff gate (only expected keys, no removals) → commit; `revert config` on any failure; `--dry-run` | **yes** (commit) |
| `nms_apply_panos_lldp.py` | FW-South: LLDP on eth1/3 + eth1/4 (profile `NMS-LLDP`), same set → diff gate → commit / revert pattern; `--dry-run` | **yes** (commit) |
| `snmpv3_walk.py` | Read-only SNMPv3 walk (e.g. LLDP-MIB `1.0.8802.1.1.2.1.4.1.1.9`) to see what NMS can read | no |
| `snmpv3_test.py` / `snmpv2_test.py` | SNMPv3 GET with the NMS credentials + wrong-password negative test / v2c `public` probe (needs a venv with `pysnmp>=7 pycryptodomex cryptography pyyaml`) | no |
| `remote_ps.py` + `*.ps1` | Read-only PowerShell on an inventory target via the console's identity-checked session pool | no |
| `pdf2txt.py` | Extract manual PDFs to text for grepping (needs `pypdf`) | no |

## SINEC NMS (visible browser)

| Script | What it does |
|---|---|
| `nms.py` | Control login (TLS pin) + read-only views: `v3options`, `scanranges`, `discovery`, `backupinfo`, `backupexec`, `set_v3_creds`, `disable_l2_ranges` |
| `nms_op.py` | Operation UI (:8443): `credcheck <ip>...` (read), `credset <ip> <SHA-1\|SHA-256>`, `credrestore` |
| `nms_ranges.py` | Create/narrow scan ranges; saves only if the enabled set == expected (ranges may not overlap, even disabled) |
| `nms_sync.py` | Press "Synchronization required" and wait until the Operation is OK |
| `nms_scan_set.py` | **Gated** scan: Operation synced + exactly the expected ranges enabled, then waits for the new job |
| `nms_wait_latest.py` | Wait for the newest discovery job; list devices |
| `nms_snmpdisc_v3.py` / `nms_snmpdisc_sha1.py` | SNMP settings for discovery: add v3 entries, disable v1/v2c (≥1 must stay enabled) |
| `nms_discovery_fix.py` / `nms_simatic_off.py` | NAT/router discovery off; SIMATIC (PLC) monitoring off |
| `nms_restr_create.py` / `nms_restr_save.py` | L1/L2 "No PROFINET discovery" restriction (name without spaces) |
| `op_ct_apply3.py` | Operation → Devices → Change device type (used for OT-FW → SCALANCE SC646 2GS00-2AC2 + `SNMPv3_sha1`) |
| `op_autotype2.py` / `op_autotype_ok.py` | "Start automatic device type change" (enables it on the Operation) |
| `op_topo_read.py` | Operation → Topology, read-only screenshot (TLS pin checked on :8443) |
| `shot.py`, `op_topo.py`, `wbm.py` | Screenshot a tab; open the topology view; generic SCALANCE WBM navigation |

**NMS UI pitfalls** (cost real time): "Start network scan" runs **immediately** (no dialog);
"Delete" sits next to "Stop network scan" in the Operations Actions menu; ag-grid checkboxes need
`.ag-selection-checkbox` clicks; several pages live in a `/monitoring/?` iframe; sessions expire
quietly — re-run `nms.py ... login`.

`scratch/` holds the one-off probes used while working out the UI (kept for reference only).
