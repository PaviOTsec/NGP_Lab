# Splunk Universal Forwarder rollout (2026-10-16)

DMZH1_SIEM (10.1.20.15, Splunk Enterprise 10.6.0.5, Enterprise term license 15 GB/day) is the
**indexer and the deployment server**. Forwarders on the lab Windows hosts phone home to it on
**8089**, pull their config as deployment apps, and send data to it on **9997**.

```
forwarder (UF) --8089 phone-home--> SIEM deployment server  (serverclass.conf -> deployment-apps)
               --9997 data--------> SIEM indexer            (index wineventlog on D:\SplunkData)
```

## Paths

| What | Where |
|---|---|
| Source of truth for the SIEM config (edit here) | `tools\splunk-uf\ds\` — mirrors `$SPLUNK_HOME\etc\` |
| Splunk home on the SIEM | `C:\Program Files\Splunk` |
| Server classes | `C:\Program Files\Splunk\etc\system\local\serverclass.conf` |
| Deployment apps (what forwarders receive) | `C:\Program Files\Splunk\etc\deployment-apps\lab_*` |
| SIEM-only apps (indexes, receiver, own logs) | `C:\Program Files\Splunk\etc\apps\lab_indexes`, `lab_siem_inputs` |
| Index data | `D:\SplunkData\<index>\` (splunkd's `NT SERVICE\Splunkd` has Modify) |
| Config backups on the SIEM | `D:\SplunkConfigBackup\splunk-etc-<stamp>.zip` (taken on every `deploy_ds.py` run) |
| Same backups on MC01 | `Backups\<date>-splunk-ds\` |
| UF installer on MC01 | `tools\splunk-uf\installer\splunkforwarder-*.msi` (operator downloads it) |
| UF installer on each host | `C:\ProgramData\LabConsole\splunk\` (+ `uf-install-<stamp>.log`) |
| UF home on each host | `C:\Program Files\SplunkUniversalForwarder` |

## Server classes → apps

| Server class | Matches | App | Gives |
|---|---|---|---|
| `lab_all_forwarders` | `*` | `lab_all_outputs` | `outputs.conf` → 10.1.20.15:9997 |
| `lab_windows` | `*` + `windows-x64` | `lab_windows_inputs` | Application, System, Security, Setup, PowerShell (+Operational), Defender, RDP session/connection, WinRM, Firewall → `wineventlog` |
| `lab_domain_controllers` | `DMZH2DC` | `lab_dc_inputs` | Directory Service, DNS Server, DFS Replication → `wineventlog` |

The SIEM is not a deployment client of itself; `lab_siem_inputs` collects its own event logs
(same channel list) and enables the `splunktcp://9997` receiver (plain TCP for the v1 setup phase).
Firewall rules `LabConsole - Splunk receiving 9997` / `management 8089` on the SIEM allow
the in-scope lab subnets only (10.1.20/24, 10.4.20/24, 10.5.20/24, 192.168.30/24, 192.168.100/24).

## Scripts

Run from the repo root with the backend venv, as with the NMS tools:

```powershell
# SIEM side (idempotent; backup first; --dry-run shows the plan; restarts Splunkd only when something changed)
.\backend\.venv\Scripts\python -I -X utf8 tools\splunk-uf\deploy_ds.py backend --dry-run
.\backend\.venv\Scripts\python -I -X utf8 tools\splunk-uf\deploy_ds.py backend

# Forwarders (`default` = the 8 hosts below; or name targets one by one)
.\backend\.venv\Scripts\python -I -X utf8 tools\splunk-uf\push_uf.py backend DMZH1_LogServer --dry-run
.\backend\.venv\Scripts\python -I -X utf8 tools\splunk-uf\push_uf.py backend DMZH1_LogServer
.\backend\.venv\Scripts\python -I -X utf8 tools\splunk-uf\push_uf.py backend default
```

`push_uf.py` checks the MSI's Authenticode signature (must be Splunk), copies it to the host
(SMB, else chunked over the shell — slow for the L4 guests, which only have PowerShell Direct),
checks sha256 on the host, runs `install_uf.ps1` (msiexec `DEPLOYMENT_SERVER=10.1.20.15:8089`,
no `RECEIVING_INDEXER`, random UF admin password), then waits up to 5 min for the `lab_*` apps to
arrive and for `Connected to idx=10.1.20.15:9997` in the forwarder's `splunkd.log`.

Default hosts: DMZH1_LogServer, DMZH1_MSSQL, DMZH2_DC, DMZH2_ADWSUS, DMZH2_MaintServer,
L4H1_RAC, L4H1_Spare, L4H1_MailServer. All reach 8089 and 9997 (checked 2026-10-16).
Not included: DMZH1_SIEM (Enterprise itself), DMZH2_EPO (off, no password), L3H1_Historian and
L4BM_OfficePC (no password yet), appliances / power-only VMs (never touched).

## Changing what forwarders collect

1. Edit or add an app under `ds\deployment-apps\` (and the class in `ds\system\local\serverclass.conf`).
   A new index goes in `ds\apps\lab_indexes\local\indexes.conf` **first** — data sent to a
   missing index is dropped.
2. `deploy_ds.py` (backs up, writes, restarts Splunkd). Forwarders pick the change up on their
   next phone-home (~60 s) and restart themselves (`restartSplunkd = true`).

Edits made in Splunk Web → Settings → Agent Management write the same `serverclass.conf`;
copy them back into `ds\` or the next `deploy_ds.py` run stops (file differs, not ours).

## Viewing it in Splunk Web

`http://10.1.20.15:8000` (http), log in with the `splunk/admin` entry of the credentials file.

| What | Where |
|---|---|
| Overview dashboard | Apps → **Lab Security** (opens *Lab Security Overview*) |
| Fired alerts | Activity → **Triggered Alerts** (or the dashboard's "Recent LAB alerts") |
| Alert definitions (enable/disable, edit) | Lab Security → **Alerts**, or Settings → Searches, reports, and alerts (app: lab_security) |
| Raw events | Search: `index=wineventlog` — always name the index; the admin role's default is only `main` |
| Forwarders | Settings → **Agent Management** (phone-home, apps, server classes) |

Handy searches (the `lab_*` macros are shared, so they work in any app):

```
index=wineventlog | stats count by host, LogName
index=wineventlog LogName=Security EventCode=4625 | `lab_failed_logon_fields` | stats count by host user src reason
index=wineventlog LogName=Security EventCode=4624 | `lab_logon_fields` | stats count by host user logon_type src
index=wineventlog LogName=Security EventCode IN (4720,4726,4728,4732,4756) | `lab_account_change_fields` | table _time host EventCode group member target_user actor
```

## Alerts (app `lab_security`, `ds\apps\lab_security\`)

12 scheduled alerts (`LAB - ...`): brute force (5+ failed logons, same account/source/host),
password spray (1 source, 4+ accounts), account lockout, user created/deleted, member added to a
privileged group, event log cleared (critical), new service, scheduled task (needs 4698
auditing), Defender malware (critical), Defender real-time protection off, suspicious PowerShell
script block (keyword list; Lab Console remoting + SDIAG troubleshooting packs excluded),
forwarder silent 15 min. Every 5 min (silent check: 15 min) over events *indexed* since the last
run; throttled per host/account. No e-mail action yet (no SMTP relay); alerts show in Triggered
Alerts and on the dashboard.

`validate_alerts.py backend -30d` lists the alerts and dry-runs each over a past window (shows
syntax errors and how often it would have fired); `splunk_search.py backend "<spl>"` or
`@file.spl` runs any read-only search (TLS pin checked before the credential is sent).
Baseline (30 d, 2026-10-16): brute force 1 (Office Workstation 10-06, expired password),
privileged group 4 (domain join 10-12), user created 1 (`SIEM` on the DC), Defender off 6
(Trellix 10-13), new service 216 (Trellix/Splunk rollouts), everything else 0.

Note: PowerShell Direct sessions from the Lab Console are logged by Windows as interactive
(type 2) logons as Administrator — expect many on L4 guests when the console used that path.

## Splunkbase apps + prebuilt detections (2026-10-16, afternoon)

| App on the SIEM | Version | Role |
|---|---|---|
| Splunk_TA_windows | 11.0.3 | Windows field extraction + CIM mapping (classic and XML) |
| Splunk_SA_CIM | 8.7.0 | data models; `ds\apps\Splunk_SA_CIM\local\macros.conf` points them at `wineventlog`/`sysmon` |
| Splunk_TA_microsoft_sysmon | 5.0.1 | Sysmon parsing; its local input collects the SIEM's own Sysmon log |
| Splunk_Security_Essentials | 3.8.3 | content browser (needs the KV store) |
| DA-ESS-ContentUpdate (ESCU) | 6.8.0 | Splunk research detections; **50 enabled** (list `escu_enabled.txt`) |

- Downloaded with `splunkbase_fetch.py` (credentials entry `splunkbase/account`), installed with
  `install_apps.py` (sha256 on the SIEM, tar.exe into etc\apps, version read back; `--upgrade`
  keeps local\). Restart afterwards with `deploy_ds.py backend --restart`.
- **XML events since 2026-10-16 ~07:20 UTC** (`renderXml = true` everywhere). The LAB alerts and the
  dashboard read both renderings (macros coalesce the XML field names with the classic `Message`
  extractions; `` `lab_win(Security)` `` matches both sources).
- **Sysmon** on all 9 hosts → index `sysmon` (see `tools\sysmon\README.md`).
- **ESCU on plain Enterprise:** `escu_select.py` picks TTP detections whose data we have (event-log
  macros, `sysmon`, Endpoint/Authentication/Change models) round-robin over priority analytic stories;
  `escu_dryrun.py` runs them read-only against the lab data; `escu_enable.py` writes
  `ds\apps\DA-ESS-ContentUpdate\local\savedsearches.conf`: enabled, hourly at its own minute,
  ES-only actions `risk`/`notable` off, `alert.track = 1` (Triggered Alerts), severity from the
  research rating. `ds\apps\DA-ESS-ContentUpdate\local\macros.conf` adds the indexes to ESCU's
  `sysmon` / `wineventlog_*` / `powershell` macros (scheduled searches can't see them otherwise).
  Tune a detection through its `<name>_filter` macro in that same local\macros.conf.
- **Security Essentials setup (2026-10-16, `sse_ui.py` in the visible Edge):** Data Inventory
  introspection done (recognised: Windows Security / PowerShell / Application / Defender, Sysmon;
  System log "introspectionFailed" - its check uses the pre-rename sourcetype, harmless). Content
  Mapping: 61 mapped (50 ESCU + 11 LAB, each LAB alert linked to the closest catalogue entry),
  49 Splunk housekeeping searches "Not A Detection". ATT&CK page: Active 60 / Available 1,529 /
  Needs data 524. Quirks: SSE hides ESCU searches unless `action.correlationsearch.enabled = 1`
  (keep ESCU's value); its content-search box only searches on **Enter**; on the ATT&CK page,
  never press "Add Bookmarks" with the default selection (it bookmarks all ~2,100 items).
- Positive test: `setspn -Q HOST/DMZH1LOGSERVER*` on LogServer → *ESCU - ServicePrincipalNames
  Discovery with SetSPN* fired (needed the lab Sysmon build with full process creation).

## Network devices via Scribbler (2026-10-19)

Plan + rule list: `docs/SPLUNK_SCRIBBLER_PLAN.md`. Switch / firewall syslog lands in Scribbler on
DMZH1_LogServer; the UF there reads it back **read-only** from Scribbler's local Elasticsearch
(127.0.0.1:9200, `_search` / `_mapping` / `_pit` only) and sends it to index **`netdev`**.

```
devices --514--> Scribbler (Logstash -> ES) <--read-- scribbler_pull.ps1 (UF scripted input, 60 s)
     -> ...\var\lib\lab_scribbler_bridge_out\<vendor>\*.log -> UF monitor -> 9997 -> index netdev
```

| Piece | Where |
|---|---|
| Bridge (deployment app, class `lab_logserver` = DMZH1LOGSERVER) | `ds\deployment-apps\lab_scribbler_bridge\` (`bin\scribbler_pull.ps1`, `.bat` wrapper, `local\inputs.conf`) |
| Bridge state / hand-off files on LogServer | `C:\Program Files\SplunkUniversalForwarder\var\lib\lab_scribbler_bridge\checkpoint.json`, `...\lab_scribbler_bridge_out\<vendor>\` (kept 7 days) |
| Parsing on the SIEM | `ds\apps\lab_netdev\` (time = Scribbler receive time UTC, host = device IP, SCALANCE fields/`event_class`, lookups `netdev_assets.csv` -> `netdev_name`/`purdue_level`, `netdev_deny_allowlist.csv`) |
| Vendor add-ons | Splunk_TA_fortinet_fortigate 1.6.10 (`fortigate_log` -> `fortigate_traffic`/`_event`), Splunk_TA_paloalto_networks 4.0.0 (`pan:log` -> `pan:system`/`pan:config`/`pan:traffic`) |
| Rules | 12 `LAB NET - ...` alerts in `lab_security` (macros `netdev_index`, `lab_net_*`) |

Line format the bridge writes: `<@timestamp yyyy-MM-ddTHH:mm:ss.fffZ> <hostIp> <body>` (SCALANCE body:
`sev= fac= prog= msg=`). Heartbeat: `index=netdev sourcetype=scribbler:bridge` (status, window, counts, error).

```
index=netdev sourcetype!=scribbler:bridge | stats count latest(_time) by host netdev_name sourcetype
index=netdev sourcetype=scribbler:bridge | table _time status fetched by_vendor.* error
index=netdev sourcetype=scalance:syslog | stats count by netdev_name event_class
```

- Dry run on LogServer (writes nothing): run `scribbler_pull.ps1 -DryRun [-From 2026-10-19T00:00:00Z]` through
  `tools\nms-onboarding\remote_ps.py` (wrap it in a scriptblock).
- Reconciled 2026-10-19 05:40 UTC: Scribbler vs Splunk counts per device identical (12 devices, 1294 events).
- Re-read everything: stop nothing on Scribbler; delete `checkpoint.json` on LogServer (next run backfills from
  Scribbler's oldest document - duplicates what is already indexed).
- Rollback: remove `lab_logserver` from `serverclass.conf` + `deployment-apps\lab_scribbler_bridge`, `apps\lab_netdev`,
  the `[netdev]` stanza and the `LAB NET` stanzas/macros, re-run `deploy_ds.py`; delete the two `var\lib\lab_scribbler_bridge*`
  folders on LogServer. Scribbler itself was never changed.
- Baseline 2026-10-19 (24 h dry run): config changed 11 (today's syslog/logging work on FW-South/FW-North/switches),
  link flapping 1 (SW-DMZ P0.4, 44 changes), deny burst/sweep/OT-protocol/OT-source 0 (DMZH2_MaintServer 192.168.30.11
  -> FW-North udp/34964 is allowlisted, operator to confirm), the rest 0.
- 2026-10-19 later: dashboard rows "Network devices" added to Lab Security Overview; 5-minute alerts now use
  staggered cron offsets (0-4) instead of `allow_skew` (skewed dispatches showed up as "Searches Delayed" in
  the health report). Security Essentials Content Mapping: all 12 LAB NET mapped (73 complete / 0 remaining):
  pipeline -> Expected Host Not Reporting (+ "in Category"), login failures -> Excessive Failed Logins, config ->
  Network Change Detected, restart -> Network Device Rebooted, link -> Detect Port Security Violation, topology/
  hardware -> External Alarm Activity, burst + sweep -> Basic Scanning, OT-protocol + from-OT -> Unauthorized
  Connection Through Firewall, firewall critical -> Unusual External Alarm. Rule tests not yet run.
- `splunk_search.py` prefixes `search ` itself: don't start a query file with `search` (it becomes a literal term
  and matches nothing). PowerShell 5.1 `Set-Content -Encoding utf8` adds a BOM - write .spl files without one.

## Correlation / risk-based alerting (started 2026-10-21)

Splunk Enterprise Security is **not** available: the SIEM's only licence is the Enterprise term licence
(15 GB/day, to 2027-10-02, no add-ons), ES is not installed, and the stored `splunkbase/account` gets
HTTP 403 for ES (app 263, restricted). If ES was bought, the entitlement is on another splunk.com account.
So correlation is built on plain Enterprise as DIY risk-based alerting, in steps:

1. **Asset lookup (done 2026-10-21)**: `make_assets.py` generates `ds\apps\lab_security\lookups\lab_assets.csv`
   from `config/inventory.yaml` (+ `EXTRA_ASSETS`: MC01; `ALIASES`: Scribbler -> DMZH1_LogServer). One row per
   key (IP, Windows host, inventory name, VM name, lower-case) -> asset, zone, role, criticality, risk_weight
   (L1 x3, L2/Plantbus x2 by inventory segment, DC/SIEM/hypervisors/MC01 x1.5, else x1), ot. Lookup
   `lab_assets` (case-insensitive) in `lab_security/default/transforms.conf`. Rerun + `deploy_ds.py` after
   inventory changes. Coverage check: all 9 Windows/Sysmon hosts and all 13 network devices resolve; Zeek
   IPs not in the inventory: 192.168.20.13/.14 (domain-joined Windows in L2, operator to identify) and
   192.168.20.149-.170 (only HTTPS check-ins to ePO 10.1.20.11) - correlation falls back to the zone weight.
   Baseline: every `drsuapi` call in the lab is DRSCrackNames/Bind/Unbind; no DRSGetNCChanges (DCSync).
2. Risk index `lab_risk` + summary-index action on the 24 LAB and 50 ESCU detections (score, technique, tactic).
3. IDS detections (Suricata high, scanners, cross-zone remote admin, RPC exec, DCSync, ICS writes, new OT device).
4. Correlation searches (score threshold, >=3 tactics, risk into L2/L1, explicit chains) -> `LAB CORR` criticals.
5. "Lab Correlation" dashboard. 6. Scripted Kali test scenario.

## Status (2026-10-16)

UF 10.6.0.5 installed and connected on all 8 default hosts (LogServer, MSSQL, DC, ADWSUS,
MaintServer, MailServer, RAC, Spare). The DC's forwarder runs as LocalSystem (the installer's
choice on a domain controller); the rest as `NT SERVICE\SplunkForwarder`.

## Lessons

- **L4/L5 → DMZ/L3 needed a FW-South change.** `Allow_NorthFirewall_Incoming/_Outgoing` use
  `service application-default`: Palo Alto App-ID opens TCP, then drops anything on a
  non-standard port (8089, 8443, 5985, ...). The denied sessions hit the unlogged default rule,
  so the traffic log shows nothing. Fixed with `tools\fw-south\allow_l4l5_dmz_l3.py` (two
  any-port rules L4/L5 <-> DMZ/L3, commit job 90; `--remove` rolls back). This also made direct
  WinRM/SMB to the L4 guests work: MSI copy 37 s over SMB vs ~37 min over PowerShell Direct.
- PAN-OS snapshot names are limited to 32 characters; a queued commit ("Commit job N is in
  progress") is not a failure, and `revert config` is refused while it runs.
- Testing HTTPS from Windows PowerShell 5.1: allow TLS 1.3 (SslProtocols 12288) — Splunk 8089,
  SINEC NMS, INS and SINEMA RC are TLS 1.3-only and fail a Tls12-only client with
  "unexpected error on send".

- `Restart-Service Splunkd` fails: splunkd's clean shutdown takes ~30 s, right at the SCM's
  30 s limit ("Cannot stop Splunkd service"), leaving the service **stopped**. `deploy_ds.py`
  waits for Stopped, then starts, and starts Splunkd whenever it finds it not running.
- Splunk Web on the SIEM is **http**://10.1.20.15:8000 (`enableSplunkWebSSL = false`).
- Restart Splunk with `splunk stop` / `splunk start` (deploy_ds.py does): a cut-short service stop
  force-kills the supervisor sidecars and the KV store fails.
- KV store "failed" on the offline SIEM = Windows root-certificate auto-update stalling local TLS
  (DNS ~7 s per internet name). Fixed by `siem_disable_root_autoupdate.ps1` (operator-run).
- The forwarder's virtual account can't read the Sysmon log until it is in Event Log Readers
  (`uf_event_log_readers.ps1`; ADWSUS: `uf_sysmon_channel_acl.ps1`). Changes go through
  `remote_change.py` (audited as changes); `remote_ps.py` is for read-only snippets.
- PowerShell 5.1 mangles embedded double quotes in native-command args: pass SPL to
  `splunk_search.py` as `@file.spl`.
