# M2-S2 — Staging Log (trainer only; do not hand out)

The single ground truth for what is planted, when, how it is undone, and which tool should see
it. The synthetic S2 rack capture, the change calendar and the answer book are all derived from
this file, so they cannot disagree with each other.

Status: **PROPOSED** (M2S2-Q2). K3 settled by M2S2-D1, SSM by M2S2-D2, port list by M2S2-D3.
Scripts in `staging/` are **drafts, untested**: kit values are placeholders until M2S2-Q4.

**All staging is done by the trainer by hand.** Claude doesn't touch kits or rack L2
(CLAUDE.md rule 13). Every planted action is read-only towards the PLC and rate-limited.

---

## 1. Rules for a reliable plant

1. **Clean S1 baseline.** Before S1 on every kit: Kali VM powered **off**, RDP **off** on the EWS,
   ET 200SP connected. Scan host is not Kali (M2S2-Q3). Otherwise K1/K2 are already "baseline".
2. **Identical on all 8 kits.** Scripts, not hand steps. Kali's MAC is fixed per kit (§3 K1), so
   the answer book is deterministic.
3. **Loud enough for a 5-min window.** Kali polls every 20–40 s (random); its gratuitous ARP for
   the borrowed IP repeats every 50–70 s.
4. **Each plant has a planned detection profile** (§5): which tools catch it and which miss it.
   The dry run confirms the profile; the answer book records what was observed.
5. **Reset proves itself.** The kit is clean only when the standard scan + `ndiff` against the
   S1 baseline is empty (§4).

## 2. The planted set

| ID | Where | What | Change type | Correct classification | Change calendar |
|---|---|---|---|---|---|
| K1 | Kit | Kali VM powered on (fixed MAC), read-only S7 polling of the CPU 410 | New | **Rogue** | no entry |
| K2 | Kit | RDP enabled on the EWS VM (registry + firewall group) | Modified | **Legitimate but undocumented** | no entry |
| K3 | Kit | ET 200SP Ethernet disconnected; CPU may go to STOP (D1) | Missing | **Temporary maintenance** | CR-0412 |
| K4 | Kit | During K3, Kali takes the ET 200SP's IP (alias + gratuitous ARP) | Modified (MAC changed) | **Rogue, hidden by K3** | not covered by CR-0412 |
| R1 | Rack DMZ | Laptop/Pi on a spare SW-DMZ port, free DMZ IP, **no gateway**; light TCP connects to DMZ servers | New | **Rogue** (SINEC confirms) | no entry |
| R2 | Synthetic S2 rack capture only | One DHCP Discover from an unknown MAC, nothing else | New | **Unresolved** (owner: site IT) | no entry |

## 3. Stage, verify, undo

### K1 — rogue S7 reader (Kali)
- **Before S1:** set Kali's NIC MAC in VirtualBox to `08:00:27:4D:32:0N` (N = kit number;
  VM powered off). Keep the VM off through S1.
- **Stage:** power on Kali; `sudo ./kali_stage.sh k1`. Starts `s7_poll.py` (CPU state + 4 bytes
  of MB0, every 20–40 s, ~10% of cycles skipped). **No writes.**
- **Verify:** `check_kit.ps1` on the EWS: Kali's IP answers; poller log on Kali shows reads.
- **Undo:** `sudo ./kali_reset.sh`; power off Kali.

### K2 — RDP on the EWS
- **Stage:** `ews_stage_k2.ps1` as administrator. Saves the original state to
  `C:\ProgramData\M2S2\k2-original.json`, sets `fDenyTSConnections=0`, enables the Remote
  Desktop firewall group, reads both back and checks 3389 is listening.
- **Undo:** `ews_reset_k2.ps1` restores exactly the saved state, then reads it back.

### K3 — ET 200SP off for maintenance
- **Stage:** unplug the ET 200SP's Ethernet cable at the switch side. Note the time. The CPU may
  go to STOP and the HMI will alarm (accepted, D1).
- **Undo (after K4 is undone, see G12):** reconnect, restart the CPU (warm restart), confirm the
  ET 200SP is back in data exchange (BF LED off, no diagnostic-buffer error).

### K4 — Kali takes the ET 200SP's IP
- **Requires:** Kali's bridged NIC on the ET 200SP's L2 segment (M2S2-G7). If not, choose
  another device on Kali's segment that K3 takes offline.
- **Stage (only after K3):** `sudo ./kali_stage.sh k4`. Refuses if anything still answers ARP
  for the IP (duplicate-address check). Adds the alias and starts the gratuitous-ARP loop.
- **Undo (before K3 is undone):** `sudo ./kali_reset.sh` removes the alias and stops the loop.

### R1 — rogue on the DMZ (rack)
- **Stage (day before, M2S2-Q8):** trainer plugs the device into a spare SW-DMZ port with a free
  DMZ IP and **no default gateway** (it can't route anywhere beyond the DMZ). Behaviour: a TCP
  connect to WSUS 10.1.20.12:8530 every few minutes, plus one slow `-sT -T2` connect scan of 3
  DMZ hosts on 80/443/445/3389. No logins. Record its MAC, IP and plug-in time in §7.
- **NMS:** left to NMS's own discovery, no manual add (D3). If it hasn't appeared by the demo,
  the trainer starts a discovery run live, which itself shows that NMS discovery is periodic.
- **Undo:** unplug after the last cohort. Whether to remove it from NMS's device list is an NMS
  change: operator's call.

### R2 — unresolved one-frame device
- Synthetic only, in the S2 rack capture spec (M2S2-T5). Nothing to stage.

## 4. Order of operations

**T-1 day:** stage R1; record §7. Confirm every kit's Kali VM has been off since S1.

**T-30 min, per kit, in this order:**
1. EWS: `ews_stage_k2.ps1` (K2).
2. Unplug the ET 200SP (K3); note the time.
3. Power on Kali; `kali_stage.sh k1`, then `kali_stage.sh k4`.
4. EWS: `check_kit.ps1` → every line PASS. This is the workbook's "deviation window is active".

**After class, per kit, in this order** (K4 before K3, G12):
1. Kali: `kali_reset.sh`; power off Kali.
2. Reconnect the ET 200SP; restart the CPU; confirm data exchange.
3. EWS: `ews_reset_k2.ps1`.
4. **Proof:** run the S1 standard scan; `ndiff` against the S1 baseline XML → **empty** (only
   timing lines). Run the collection script; `Compare-Object` against S1 shows no new listener
   and no unknown neighbour.
5. Record in §7.

## 5. Detection matrix (answer key and debrief slide)

✔ catches · ✖ misses · values in `<>` come from the dry run. Menu names in WBM/NMS/SSM are to be
confirmed on the real versions.

| | Wireshark | Nmap + `ndiff` | PowerShell (EWS) | Kit switch | NMS / SSM | Change calendar |
|---|---|---|---|---|---|---|
| **K1** | ✔ new MAC `08:00:27:4D:32:0N` in Endpoints ▸ Ethernet; `s7comm && ip.src != <EWS_IP>` | ✔ `+` new host `<KALI_IP>` | ✔ `Get-NetNeighbor` shows `<KALI_IP>` | ✔ two MACs on the EWS port (S3 port-security lead-in) | ✖ kit not monitored | no entry → Rogue |
| **K2** | ✖ unless someone connects (`tcp.port == 3389`) | ✔ `+3389/tcp open ms-wbt-server` (D3) | ✔ `Get-NetTCPConnection -State Listen -LocalPort 3389`; `fDenyTSConnections = 0`; firewall-rule event gives the **time** | ✖ | ✖ | no entry → Legitimate but undocumented (an engineer's convenience, no ticket) |
| **K3** | ✔ `eth.addr == <ET200SP_MAC>` → 0 frames; PROFINET cyclic frames gone; repeated `pn_dcp` Identify from the CPU expected (confirm) | ✔ `-` host (ARP sweep only, M2S1-P4) | ✖ | ✔ port link down | ✖ | CR-0412 → Maintenance |
| **K4** | ✔ `arp.src.proto_ipv4 == <ET200SP_IP>` → sender MAC is VirtualBox, not Siemens. `arp.duplicate-address-detected` only if both MACs fall in one capture | ✖ IP "still up" → looks unchanged (MAC line in `ndiff` to confirm) | ✔ only if the EWS shares the segment: `Get-NetNeighbor -IPAddress <ET200SP_IP>` → `08-00-27-…` | ✔ ET 200SP's IP behind the EWS port's second MAC | ✖ | CR-0412 says "offline", not "replaced" → Rogue |
| **R1** | ✔ in the S2 rack capture: `eth.src == <R1_MAC>` | — rack not scanned | — | — | ✔ NMS device list after discovery; SSM new-asset / scan alert with **first seen** (D2, provisional) | no entry → Rogue |
| **R2** | ✔ `dhcp` → exactly 1 frame | — | — | — | ✖ | no entry → Unresolved (one frame isn't enough) |

**Debrief points:**
- Reflection Q1: K1 is caught by everything on the kit; R1 is the only one SINEC catches.
- Reflection Q2: K4 hides inside K3's maintenance window. A real module swap brings a new
  **Siemens** MAC; this one is VirtualBox.
- Reflection Q3: continuous monitoring on the kit network (SSM sensor on the kit uplink) would
  have caught K1 and K4 when they happened, not at the next diff.

## 6. Change calendar (draft handout, issued at checkpoint 1)

| CR | Window | System | Work | Status |
|---|---|---|---|---|
| CR-0409 | Day before, 16:00–17:00 | WSUS (DMZ) | Monthly update approval sync | Completed |
| CR-0412 | Session day, 08:30–12:00 | Kit ET 200SP | I/O module swap. ET 200SP offline during the window; controller may stop | Approved |
| CR-0415 | Session day, 14:00–15:00 | SC646-2C | Firewall rule review (read-only, no change) | Approved |

## 7. Staging record (fill in on the day)

| Kit | Kali MAC | Kali IP | K2 staged | K3 unplugged | K1/K4 staged | Check PASS | Reset done | Empty diff |
|---|---|---|---|---|---|---|---|---|
| KIT01 | 08:00:27:4D:32:01 | | | | | | | |
| KIT02 | 08:00:27:4D:32:02 | | | | | | | |
| KIT03 | 08:00:27:4D:32:03 | | | | | | | |
| KIT04 | 08:00:27:4D:32:04 | | | | | | | |
| KIT05 | 08:00:27:4D:32:05 | | | | | | | |
| KIT06 | 08:00:27:4D:32:06 | | | | | | | |
| KIT07 | 08:00:27:4D:32:07 | | | | | | | |
| KIT08 | 08:00:27:4D:32:08 | | | | | | | |

**R1:** MAC ______ · IP ______ · SW-DMZ port ______ · plugged in ______ · first seen NMS ______
· first seen SSM ______
