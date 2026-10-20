# Plan: Scribbler (network-device syslog) → Splunk, plus detection rules

Status: **approved 2026-10-19; Steps 0–3 and the 12 rules deployed 2026-10-19** (record:
`tools/splunk-uf/README.md` → "Network devices via Scribbler"). Still open: dashboard row, Security
Essentials mapping, live/replay tests (section 5). Deviations from the text below: the bridge writes to
`$SPLUNK_HOME\var\lib\lab_scribbler_bridge_out\` (the UF account already owns it, so no ACL change), and the
asset lookup outputs `netdev_name` (the PAN add-on sets `dvc_name` itself). Written for the agent doing
the syslog onboarding (`tools/syslog-onboarding/`). Read CLAUDE.md first; rules 5, 12, 13 and 14 apply to
every step. Items marked **[operator]** need confirmation before they run.

Operator decisions so far:
- **Integration route approved:** the Splunk UF on DMZH1_LogServer pulls from Scribbler (section 2).
- **Detections:** start with a small basic set (10–20 rules) that can actually be tested (section 4).
- **The firewalls log denied traffic only**; accepted/forwarded traffic is not logged.
- The Lab Console audit log is **not** linked to Splunk. Nothing in this plan depends on it.

## 1. What exists today (2026-10-19)

| Piece | Fact |
|---|---|
| Scribbler 1.15.35 | On DMZH1_LogServer 10.1.20.13 (Windows Server 2022, not an appliance). Services `ScribblerService`, `ScribblerLogStashService`, `ScribblerElasticSearchService` under `C:\Syskey\Scribbler\`. |
| Storage | Elasticsearch 8.19.15, `http://localhost:9200`, no auth from the local host. Index pattern `scribbler*`. |
| Stored fields | `@timestamp` (receive time, UTC), `hostIp`, `host`, `message`, `syslog_pri`, `syslog_severity_code`, `syslog_facility_code`, `syslog_program`, `syslog_process_id`, `syslog_host`, `syslog_timestamp`, `syslog_message_format`, `syslog_message_id`, `ingest_protocol`, `hash`. |
| Switches | SW-DMZ, SW-Ops, SW-WAN, SW-Ent, SW-L2, SW-PCS, SW-SIS, SW-SAS (SCALANCE, RFC 5424; `syslog_program` = order number `6GK5...`; body like `[meta sysUpTime="…"] SSH: User admin has logged in from 192.168.20.189.`). SW-Mgmt pending (no gateway). |
| Firewalls | **FW-North** 10.4.20.254 (FortiOS key=value): implicit-deny + local-in deny traffic, plus event logs. **FW-South** 10.1.20.254 (PAN-OS, BSD syslog, CSV body): System + Config logs + `interzone-default` denies. **OT-FW** SC646-2C 192.168.20.254 (SCALANCE format): events only (cold/warm start, link, auth failure, power, fault, security log, NTP, config change); its firewall function is off, so it sends no traffic logs. |
| Time | All switches and firewalls sync to SINEC INS 10.1.20.21 (NTP), so device timestamps are correct. |
| Splunk | DMZH1_SIEM 10.1.20.15 = indexer + deployment server (`tools/splunk-uf/README.md`). DMZH1_LogServer already runs a UF connected to it. |

Notes for the rules:
- FW-North sessions opened before the deny-only change can still send interim **accept** logs
  (`logid 0000000020`) until those sessions end. Rules must filter on `action` = deny/blocked, never on "any traffic log".
- DMZ/L3 → L2 sessions are source-NATed by FW-South to **192.168.20.189**. An L1/L2 switch login therefore
  shows `from 192.168.20.189`, not the real client.

## 2. Integration design (approved)

```
devices --UDP 514--> Scribbler/Logstash --> Elasticsearch (localhost:9200)
                                                 |  read-only query every 60 s
                                    UF scripted input (PowerShell) on LogServer
                                                 |  appends to per-vendor files
                                    UF monitor inputs --9997--> SIEM, index netdev
```

There are no changes on the devices or in Scribbler's configuration. Scribbler remains the receiver and system of record.

## 3. Build steps

### Step 0: decisions **[operator]**
1. Index name `netdev` and retention (proposal: 180 days, `D:\SplunkData\netdev`).
2. Download **Fortinet FortiGate Add-On for Splunk** and **Splunk Add-on for Palo Alto Networks** from
   Splunkbase (`splunkbase_fetch.py`, account `splunkbase/account`). Use the input sourcetype each one documents
   (historically `fgt_log` and `pan:log`).

### Step 1: SIEM side (`tools/splunk-uf/ds/`, then `deploy_ds.py --dry-run`, then for real)
- `apps/lab_indexes/local/indexes.conf`: add `[netdev]` **before** any data is sent (events for a missing index are dropped).
- New SIEM app `apps/lab_netdev/` (add it to `deploy_ds.OWNED`):
  - The bridge writes one event per line: `<@timestamp yyyy-MM-ddTHH:mm:ss.fffZ> <hostIp> <body>`. There are no
    commas before the body, so PAN's comma-counted extractions still line up. For SCALANCE the body is
    `sev=<n> fac=<n> prog=<syslog_program> msg=<message>`.
  - `props.conf` for our sourcetypes (`scalance:syslog`, `scribbler:bridge`): `TIME_PREFIX = ^`,
    `TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%3N%Z`, `MAX_TIMESTAMP_LOOKAHEAD = 30`, `SHOULD_LINEMERGE = false`.
    The vendor add-ons keep their own timestamp settings; device time is correct now that everything uses NTP.
  - Index-time transform on every netdev sourcetype: `host` = the second token (device IP). Use distinct
    `TRANSFORMS-lab_*` class names so the add-ons' own stanzas still apply.
  - Lookup `netdev_assets.csv` (ip, name, purdue_level, vendor, model, criticality), automatic on all netdev
    sourcetypes. Include the out-of-inventory devices (SW-L2/PCS/SIS/SAS, OT-FW) as rows only. A lookup is
    passive and contacts nothing.
  - SCALANCE search-time extractions (`user`, `src`, `port`, `action`, `event_class`) and CIM tags
    (`authentication`, `change`). **Harvest the real message templates first.** Run a read-only ES terms
    aggregation on `message`, with numbers normalised, across all SCALANCE senders, including OT-FW, and check it
    against the SCALANCE event documentation. Mark any template not yet seen live as *unverified*.
  - Macro `` `netdev_index` `` (= `index=netdev`). Rules use
    the macro so they can be pointed at a test index.
- `apps/Splunk_SA_CIM/local/macros.conf`: add `netdev` to `cim_Authentication_indexes`,
  `cim_Change_indexes`, `cim_Network_Traffic_indexes`.
- Install the add-ons with `install_apps.py`, then run `deploy_ds.py backend --restart`.

### Step 2: the bridge on LogServer (deployment app `lab_scribbler_bridge`)
- Server class `lab_logserver`, whitelist `DMZH1LOGSERVER`, `restartSplunkd = true`.
- `bin/scribbler_pull.ps1` via `[script://...]` (a wrapper calling `powershell.exe -NoProfile -ExecutionPolicy
  Bypass -File`), `interval = 60`, sourcetype `scribbler:bridge`, index `netdev`.
  - Window `[checkpoint, now − 60 s)`, half-open, sorted by `@timestamp`. Page with PIT + `search_after`
    (`_shard_doc` tiebreaker; ES 8 doesn't allow sorting on `_id`). Advance the checkpoint to the upper bound
    only after every page has been written.
  - Classify by content: `syslog_program` starts with `6GK5` → `scalance` (switches **and OT-FW**);
    `devname=` / `logid=` → `fortigate`; CSV body with `,TRAFFIC,|,SYSTEM,|,CONFIG,|,THREAT,` → `paloalto`;
    `hostIp=127.0.0.1` with `"Application": "ScribblerLogManager"` → `scribbler`; else `unknown`.
  - Append to `C:\ProgramData\LabConsole\scribbler-bridge\out\<vendor>-yyyyMMdd.log` (UTF-8, no BOM, `\n`) and
    delete files older than 7 days. One `[monitor://...]` per vendor with its sourcetype: `scalance:syslog`, the
    FortiGate input sourcetype, the PAN input sourcetype, `scribbler:audit`, `scribbler:unknown`.
  - Keep state in `checkpoint.json` in the same folder. The first run backfills from the oldest Scribbler document.
  - stdout: one JSON heartbeat per run, `{status, es_ok, window_from, window_to, fetched, by_vendor{}, error}`.
    If `hostIp`, `message` or `@timestamp` are missing from the mapping, report `error`, which catches a Scribbler
    upgrade that changes the schema.
  - Toward Scribbler it only calls `_search` and `_pit` open/close, so it is read-only.
- Give `NT SERVICE\SplunkForwarder` Modify on the output folder via `remote_change.py` (audited) and read the ACL back.
- **Dry run first:** run the script through `tools/nms-onboarding/remote_ps.py` in a print-only mode (first 20
  lines per vendor, nothing written) and review the output before deploying.

### Step 3: validation
- **Reconcile counts.** For the same 24 h window, compare the ES aggregation by `hostIp` with
  `` `netdev_index` | stats count by host ``. They must match exactly.
- Check that the add-ons rewrite sourcetypes (`fortigate_traffic`/`fortigate_event`,
  `pan:traffic`/`pan:system`/`pan:config`) and that `tag=authentication`, `tag=change` and the deny traffic return
  events with the expected `action`, `user`, `src`, `dest` and `dest_port` fields.

## 4. Detection rules (12)

Conventions match the existing `LAB - ...` alerts. They live in `apps/lab_security/default/savedsearches.conf` as
`LAB NET - ...`, run every 5 min over indexed time, are throttled per device/source, and use `alert.track = 1`. Lists belong in
lookups, not in the SPL. Severity is raised one step when the device's `purdue_level` is 1 or 2.

Test types: **Live** means a real action on an L3+ device, and every live test needs operator go-ahead. **Replay** means sample
lines are loaded into a test index (see section 5); it is used where a live test would be disruptive or would need L1/L2.

| ID | Rule | Logic | Sev | Test |
|---|---|---|---|---|
| **Pipeline** | | | | |
| NET-01 | Log pipeline broken | No `scribbler:bridge` heartbeat for 10 min, or heartbeat with `es_ok=false`/`error`, or a LogServer System 7036/7031/7034 event for a `Scribbler*` service stopping or crashing (already in `wineventlog`) | high | Live: disable the bridge input in its deployment app, wait 10 min, then re-enable |
| NET-02 | Network device stopped logging | Daily: a device in `netdev_assets.csv` with events in the previous 7 days and none in 48 h | medium | Dry run with the window shortened to 1 h |
| **Every device (switches + firewalls, via CIM tags)** | | | | |
| NET-10 | Admin login failures | `tag=authentication action=failure`, ≥3 per device+src in 10 min (SCALANCE auth failure, FortiOS admin login failed, PAN system auth-fail) | medium | Live: 3 wrong-password SSH attempts to **SW-DMZ**, then to **FW-North**. First check the lockout threshold so the account doesn't lock |
| NET-12 | Configuration changed | `tag=change` from any device: SCALANCE "configuration changed", FortiOS config/attribute events, PAN config log + commit. Include who and what in the alert | medium | Live: a cosmetic change, reverted (e.g. system contact on SW-DMZ; a comment on a FW-North address object). Backup first |
| **Switches + OT-FW (SCALANCE events)** | | | | |
| NET-13 | Device restarted | Cold/Warm start event | medium | Replay (live only if the operator picks a switch that can be rebooted) |
| NET-14 | Link change on OT/L2 switch | Link down/up on SW-L2/PCS/SIS/SAS or OT-FW; or ≥5 link changes on one port in 10 min on any switch (flapping) | high | Live (flapping part): unplug and replug a spare port on SW-DMZ 5 times. Replay for L1/L2 |
| NET-15 | Topology, loop or hardware alarm | Ring/MRP, spanning tree, loop detection, fault state, power change, diagnostics alarm | high | Replay |
| **Firewalls (deny logs + system logs)** | | | | |
| NET-20 | Denied traffic burst | ≥50 denies from one src in 5 min (FW-North implicit/local-in deny, FW-South `interzone-default`) | medium | Live: one probe run from **L4H1_Attacker_Win**, described below |
| NET-21 | Port or host sweep | One src denied on ≥20 distinct dest ports, or ≥20 distinct dest IPs, in 5 min | high | Live: same probe run |
| NET-22 | Denied industrial-protocol attempt | Deny with `dest_port` in 102, 502, 2404, 4840, 20000, 34962–34964, 44818, 47808 (S7, Modbus, IEC 104, OPC UA, DNP3, PROFINET, EtherNet/IP, BACnet) | high | Live: same probe run includes port 502 |
| NET-23 | Denied traffic from OT | Deny where `src` is in 192.168.1–4.0/24 or 192.168.20.0/24 (an OT device trying to reach something it may not) | high | Replay |
| NET-24 | Firewall critical system event | PAN system log severity critical/high, FortiOS event level alert/critical/emergency (HA, link, disk, licence, dataplane) | high | Replay |

**The probe run (NET-20/21/22)** needs operator go-ahead and must never target L1/L2. From L4H1_Attacker_Win, make one TCP connect
attempt to each of 25 ports, including 502, on **one** DMZ/L3 address that a firewall *denies*. Repeat it 3 times, about 75 attempts in total. First
make a single attempt and confirm the deny reaches Splunk. If the path turns out to be allowed, pick another target or port with the operator.

## 5. Testing method
- **Replay:** create a `netdev_test` index with the same props. Build sample files per sourcetype from real
  messages harvested from Scribbler. For templates not seen live yet (restart, loop, fault, PAN/FortiOS critical),
  use the vendor's documented wording and mark them *unverified*. Load the files with `splunk add oneshot` on the SIEM using the
  real sourcetype, then dry-run each rule with `` `netdev_index` `` pointed at `netdev_test`
  (`validate_alerts.py`). Delete the test index afterwards.
- **Before enabling:** run `validate_alerts.py backend -7d` over `netdev` to see how often each rule would have fired,
  and tune the thresholds or lookups where it is noisy.
- Record every test (what, when, alert fired yes/no, time to fire) in `tools/splunk-uf/README.md`.

## 6. Dashboard
Add a "Network devices" row to *Lab Security Overview* with events per device/level, a last-seen table, denies per
firewall over time, bridge health, and recent `LAB NET` alerts. Add the NET rules to Security Essentials Content
Mapping (`sse_ui.py`).

## 7. Rollback
- SIEM: `deploy_ds.py` backs up the config on every run (`D:\SplunkConfigBackup\`). Remove `lab_netdev`, the
  add-ons, the `netdev` stanza (data stays on disk until deleted) and the `LAB NET` searches.
- LogServer: remove `lab_scribbler_bridge` from the server class (the UF deletes it on phone-home), then delete
  `C:\ProgramData\LabConsole\scribbler-bridge\`. Scribbler itself is never changed.

## 8. Later (not in this round)
- Login attribution for L1/L2: join switch logins from 192.168.20.189 to Sysmon EventCode 3 (dest port 22/443)
  to name the real client.
- After the firewall add-ons populate `Network_Traffic`, shortlist ESCU network detections with `escu_select.py`.
- Hardening: ES on LogServer accepts unauthenticated localhost requests (Scribbler's to configure); TLS on 9997.
