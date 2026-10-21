# IDS sensor L4H1_IDS — Zeek + Suricata → Splunk (built 2026-10-20)

Passive network sensor fed by the SPAN aggregator (all switch mirror sessions from 2026-10-19/20 →
one cable). Operator request: Ubuntu Server VM on L4-HOST-1 (least-loaded host), one NIC on WAN,
one left unconnected for the aggregator; everything else automated from MC01.

| | |
|---|---|
| VM | `L4H1_IDS` on L4-HOST-1, Gen2, Secure Boot (UEFI CA template), 12 vCPU, 32 GB static, no auto-checkpoints, auto-start |
| Disks | `D:\Hyper-V\IDS-SENSOR\L4H1_IDS\Virtual Hard Disks\` — `-os.vhdx` 80 GB (LVM /), `-data.vhdx` 500 GB (`/data`, ext4 label IDSDATA) |
| NIC `mgmt` → guest `mgmt0` | vSwitch WAN, static MAC 00155DA981E0, **10.5.20.60/24**, gw 10.5.20.254, DNS 10.1.20.17 |
| NIC `capture` → guest `cap0` | **not connected** (operator attaches it), static MAC 00155DA981E1, no IP, promisc, offloads off |
| OS | Ubuntu 24.04.5 LTS, kernel 6.8.0-147, hostname `l4h1-ids`, NTP → SINEC INS 10.1.20.21 |
| Login | `idsadmin`, key `C:\Users\Administrator\.ssh\l4h1_ids_ed25519` (credential `L4H1_IDS/idsadmin`; password = console/sudo fallback; passwordless sudo) |
| SSH host keys | rsa `SHA256:viOS59fOQDXiWSTfDKHXqZ9RDaGD6OsVxw/Bt0x9RJM` (pinned in inventory), ed25519 `SHA256:+DXgu1pnS/AnmsyguFvO0pxMpOnjeFV4pfwjbcllr90` — both matched cloud-init's console print before first login |
| Suricata | 8.0.7 (OISF PPA), af-packet `cap0` 4 threads, ET Open 53,231 rules, EVE (alert/anomaly/stats, community-id) → `/data/suricata/eve.json`, Modbus/DNP3/ENIP parsers on |
| Zeek | 9.0.0 (OBS security:zeek), zeekctl cluster logger+manager+proxy+4 af-packet workers, JSON logs → `/data/zeek/logs`, 30-day expiry, community-id, known hosts/services, Modbus master/slave tracking |
| ICSNPP | s7comm (+COTP, S7Comm Plus), opcua-binary, enip/CIP, modbus, dnp3, bacnet. **profinet-io-cm left out** (its .hlto doesn't load on Zeek 9.0.0) |
| Splunk | UF 10.6.0.5 → DS 10.1.20.15:8089 → class `lab_ids_sensor` → `lab_ids_inputs`; indexes **`zeek`** (60 GB/30 d) and **`suricata`** (20 GB/90 d) |

## Splunk side (DMZH1_SIEM, from `tools/splunk-uf/ds`, deployed with `deploy_ds.py --force`)

- `apps/lab_indexes` — `zeek`, `suricata` indexes on D:.
- `apps/lab_ids` — line breaking + timestamps (the CCX Suricata TA assumes syslog and line-merges).
- `apps/Splunk_SA_CIM/local/macros.conf` — the new indexes added to Network_Traffic, Network_Resolution,
  Authentication, Intrusion_Detection, Alerts, Web, Certificates.
- `deployment-apps/lab_ids_inputs` — monitors `/data/zeek/logs/current/*.log` (sourcetype `bro:json`,
  retyped per file to `bro:conn:json` etc.) and `/data/suricata/eve.json` (sourcetype `suricata`).
- Add-ons (Splunkbase, `splunkbase_fetch.py zeek suricata` + `install_apps.py`): **Splunk_TA_zeek 1.0.11**
  (Corelight/Aplura; Splunk's own Zeek TA 1617 is archived since 2018) and **Splunk_TA_CCX_Suricata 1.0.1**.
  Both are developer-supported, config-only (no scripts).

Check: `index=zeek OR index=suricata host=l4h1-ids | stats count by index, sourcetype`.

## How it was built (rerunnable)

1. MC01 downloads the ISO (sha256 vs releases.ubuntu.com) and the UF .deb (sha512 vs splunk.com) into
   `C:\Users\Administrator\Downloads\ids-sensor\`.
2. `make_seed.py` (scratch venv: pycdlib, passlib, pyyaml) → CIDATA seed ISO with the autoinstall
   (static network matched by MAC, LVM on the smallest disk, key + SHA-512 password hash).
3. Temporary `python -m http.server 8088 --bind 192.168.100.18` on MC01; `create_vm.ps1` (via
   `tools/splunk-uf/remote_change.py`) pulls both ISOs onto the host, checks hashes, builds and verifies the VM.
   (`stage_to_host.py` is the slow fallback: parallel WinRM chunks, ~5 MB/s.)
4. Start; answer the installer's "Continue with autoinstall? (yes|no)" with `vm_console.py keys L4H1_IDS yes`
   (TypeText does not register at that prompt; TypeKey does). `vm_console.py screen` = console screenshot.
5. VM powers off → `post_install_vm.ps1` ejects the ISOs (by controller location — piping drive
   objects silently left one mounted), boots from the OS disk, starts.
6. `ssh_run.py hostkey` → compare with the console → pin in the inventory.
7. `mini_proxy.py 10.1.20.56 3128 10.5.20.60` on MC01 (only the VM may use it; logs every destination),
   then `ssh_run.py stage L4H1_IDS base|suricata|zeek`, `ssh_run.py put` the .deb, `stage ... uf <deb>`.
8. Reboot; `stage ... status`.

The http server and proxy were stopped afterwards; the seed ISO (password hash) was deleted from the
host and MC01. The VM keeps `/etc/apt/apt.conf.d/95labproxy` → 10.1.20.56:3128: apt/rule updates work
only while `mini_proxy.py` runs.

## Operating it

- **Rule updates** (no internet in the lab): start `mini_proxy.py` on MC01, then
  `ssh_run.py run L4H1_IDS "sudo https_proxy=http://10.1.20.56:3128 suricata-update && sudo systemctl reload suricata"`.
- **Tuning** (there is no auto "learning mode"): run 1–2 weeks with everything alerting, then quiet noisy
  SIDs in `/etc/suricata/disable.conf` / `threshold.config` (suricata-update) and promote what's left to
  Splunk alerts. Zeek's known_hosts/known_services give the "new device/service" baseline.
- **Capture feed (connected 2026-10-21, `connect_span.ps1`)**: the aggregator cable is in L4-HOST-1
  **Embedded NIC 2** (Broadcom NetXtreme Gigabit Ethernet, MAC 4C:C5:D9:E3:82:D0; the only connected NIC
  outside the SET teams; it had only an APIPA address). External vSwitch **`SPAN`** on it
  (`AllowManagementOS $false`, no teaming), VM adapter `capture` on `SPAN` with `-PortMirroring Destination`
  and VLAN trunk 1-4094 (native 1), external port feature *Ethernet Switch Port Security Settings*
  `MonitorMode = 2` (Source), so frames not addressed to the VM reach it. All done as HyperVAdmin.
  `Get-NetAdapter`/`Get-NetLbfoTeam` are Access Denied for HyperVAdmin: use `Win32_NetworkAdapter` and
  `Msvm_ExternalEthernetPort` to find NICs. Check the feed with `sudo bash ~/capture_check.sh`
  (`capture_check.sh`: rate, VLANs, top conversations, Zeek capture_loss, Suricata kernel drops).
- **First look (2026-10-21)**: ~35-40 pps / ~115 kbit/s, IPv4 only, no VLAN tags, 13 source MACs in 60 s;
  DMZ 10.1.20/24, WAN, L4, Historian and routed 192.168.20/24 traffic; almost no L1 and no OT Layer-2
  (PROFINET/MRP/LLDP). Looks like the DMZ-side feed only, not all 8 switches; operator to confirm the
  aggregator inputs. The sensor's own UF traffic (10.5.20.60 -> 10.1.20.15:9997) is in the feed (filter later).
- **Smoke test** (`ids_smoke_test.sh`, run from Kali as `kali`, no sudo): nmap top-100 service scan + NSE
  http-title + Nikto/sqlmap/masscan user-agents against the SIEM. 2026-10-21: Zeek logged all of it (157 conns,
  100 ports, every user-agent in http.log); Suricata fired ET SCAN Nmap UA (18), Masscan, RDP-from-Nmap, but
  **not** the Nikto/sqlmap rules: those are `$EXTERNAL_NET -> $HOME_NET` and HOME_NET is all RFC1918, so
  lab-internal attackers never match.
- **EXTERNAL_NET (operator, 2026-10-21; `provision.sh extnet`)**: `EXTERNAL_NET = [$PUBLIC_NET,$LAB_UNTRUSTED_NET]`,
  `LAB_UNTRUSTED_NET = [10.5.20.0/24,192.168.20.0/24]` (WAN + OT L2), `PUBLIC_NET` = complement of RFC1918
  written out (a range can't be re-added inside `!$HOME_NET`). HOME_NET unchanged (all RFC1918), so attacks
  inside those subnets still match. Edited in `suricata.yaml` itself (vars can't go in the include); original
  is `/etc/suricata/suricata.yaml.bak-20261021-105410`. Re-test: 19 alerts -> 12 signatures incl. sqlmap,
  /etc/passwd-in-URI, NSE user-agent, DB-port probes. Nikto rule needs 5 hits/60 s (test sends 1).
  No new alerts on normal traffic in the first 12 min. Rollback: copy that backup back, `systemctl restart suricata`.
- **Unix socket (fixed 2026-10-21, `provision.sh runsock`)**: after a reboot `/run/suricata/` was missing and
  user `suricata` couldn't create it (no `suricatasc`). `/etc/tmpfiles.d/suricata-lab.conf` now recreates it
  at boot, owned by suricata. Check: `sudo suricatasc -c uptime /run/suricata/suricata-command.socket`.
- **Dashboard (2026-10-21)**: Splunk > Lab Security > **IDS Overview** (`lab_ids_overview.xml` in
  `tools/splunk-uf/ds/apps/lab_security`, Simple XML). Rows: KPIs, IP focus (appears when an IP is set or
  clicked), Suricata alerts (over time, signatures, sources, targets), zone-to-zone matrix + cross-zone
  services, recon/lateral (scanners, remote access across zones, PsExec/schtasks/WMI/DCSync over RPC),
  DNS failures / HTTP user agents / TLS names, ICS conversations + writes/control actions, newest hosts /
  services / software (30 d), sensor health. Zones come from lookup `lab_zones` (`lookups/lab_zones.csv`,
  CIDR match, exported globally); macros `ids_*` in `lab_security/default/macros.conf`.
  Zeek's own `host` field (known_hosts, known_services, software, http) collides with Splunk's `host`
  (= l4h1-ids) and arrays become `field{}`: read them with `spath`. Permissions: app default (everyone
  reads) for now; operator will restrict later.
- **Volume**: once traffic flows, watch licence use (15 GB/day): `index=_internal source=*license_usage.log type=Usage idx IN (zeek,suricata)`.

## Known issue found during the build (not changed)

DMZH1_SIEM's clock is ~52 s behind (it syncs from its Hyper-V host via VM IC time sync, not NTP), so
events from NTP-synced sources (this sensor, switches, firewalls) index with negative lag. Fixing it
(disable VM time-sync IC / point w32time at 10.1.20.21) is the operator's call.

## Rollback

1. SIEM: remove the `lab_ids_sensor` class from `ds/system/local/serverclass.conf`, delete
   `ds/apps/lab_ids`, `ds/deployment-apps/lab_ids_inputs`, revert `lab_indexes` + CIM macros, `deploy_ds.py --force`
   (config backups `Backups\20261020-splunk-ds\splunk-etc-20261020-174318.zip` = state before this change).
   Remove `Splunk_TA_zeek`, `Splunk_TA_CCX_Suricata` from `etc\apps`. Index data: `D:\SplunkData\zeek|suricata`.
2. Host: SPAN feed only: `Disconnect-VMNetworkAdapter -VMName L4H1_IDS -Name capture; Remove-VMSwitch SPAN -Force`
   (Embedded NIC 2 goes back to the host stack). Whole VM: `Stop-VM L4H1_IDS -TurnOff; Remove-VM L4H1_IDS`,
   delete `D:\Hyper-V\IDS-SENSOR\`.
3. MC01: remove the `L4H1_IDS` inventory entry and `L4H1_IDS/idsadmin` credential
   (backup `config\credentials.example.yaml.bak-20261020-ids`), delete `~\.ssh\l4h1_ids_ed25519*`.
