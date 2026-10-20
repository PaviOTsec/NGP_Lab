# M1 S2 — Refined Tables + Hypothesised Answer Key

**Status: DRAFT / PROPOSED.** The injection below is a **hypothesis** used so the answer key has
real content; the operator will finalise the actual showcase (S2-Q12). Every S7comm field value
is marked *to confirm against the real capture in the kit's Wireshark version*.

Companion to `../M1_S2_TRACKER.md`. Decisions in play: S7comm only (S2-D8); live Kali injection
driving physical lights, reset by hardware buttons (S2-D9); dedicated mirror port + USB capture
NIC (S2-D7).

---

## 1. Design principles — why this is less clerical than the workbook

The workbook has seven tables (W2.1–W2.7). Two of them (W2.6 "document every flow", and the
W2.5/W2.7 pair) are mostly transcription. In a kit there are only a handful of real flows, so
the clerical load comes from **re-deriving things students already know** and from **splitting
one idea across several grids**. Three moves fix it:

1. **Pre-fill the known.** Device IPs, MACs and roles come from the Session-1 inventory and the
   Kit Parameter Sheet. Those cells are printed for the students; they don't re-type them.
2. **Merge overlapping grids.** Protocol-usage + traffic-documentation become one *flow* table.
   Protocol-comparison + security-summary become one *attack-anchored* table.
3. **Make the columns reasoning-shaped.** Instead of flat "write down what you see", columns run
   **observed → expected → deviation → evidence**, so filling the table *is* the analysis.

The refined set is **five tables (T1–T5)** and still maps 1:1 to the workbook deliverables, so
sign-off is unaffected:

| Refined | Covers workbook | Change |
|---|---|---|
| T1 SPAN Configuration Record | W2.1 | kept (short, change-management evidence) |
| T2 Flow Snapshot | **W2.2 + W2.6** | merged; roles pre-filled; adds "expected?" column |
| T3 Baseline vs Anomaly | **W2.4** (reframed) | the keystone analytical table |
| T4 S7comm Packet Dissection | W2.3 | kept, capped at ~5 focused packets |
| T5 Security Assessment (attack-anchored) | **W2.5 + W2.7** | merged; tied to the write they saw |

Classroom effect: ~15 min of transcription (old W2.6 + W2.5/W2.7 copying) becomes ~15 min of
reasoning (T3 + T5), with the same evidence artefacts at the end.

---

## 2. Hypothesised injection (so the answer key is concrete)

> **HYPOTHESIS — replace with the finalised showcase (S2-Q12).** Values are examples; the IP
> scheme is per the Kit Parameter Sheet (S2-Q1). Assumes EWS, Kali and the CPU 410 are reachable
> at layer 2 on the mirrored segment, which the S2-D7 wiring implies.

| Item | Hypothesised value | Note |
|---|---|---|
| Attacker host | Kali VM, `<ATTACKER_IP>` e.g. 192.168.10.66 | **Not on the architecture** — the primary tell |
| Attacker MAC | VirtualBox/NIC OUI (e.g. `08:00:27:…`) | Non-Siemens OUI stands out next to `…:Siemens` controllers |
| Target | CPU 410 `<PLC_IP>` e.g. 192.168.10.10, TCP **102** | S7comm over TPKT/COTP |
| Action | S7comm **Write Var** (`s7comm.param.func = 0x05`) to the **output area** (`area = 0x82`), forcing bits that drive the **lights** | Legit HMI writes target **DBs (0x84)**, not the output image — the "weird" marker |
| Cadence | a short burst, or every ~10 s | Different rhythm from the ~1 s read-polling baseline |
| Physical effect | some lights turn ON | Reset with the hardware button |
| "Weird" markers (intentional) | new node + non-Siemens MAC; **writes with no prior read-polling**; **direct output forcing**; off-cadence | Findable by beginners, yet still a structurally valid packet (debrief point) |

**Baseline (normal) for contrast:**
- **HMI/EWS `<HMI_WS_IP>` → CPU 410:** S7comm `Setup communication` (0xF0) once, then cyclic
  **Read Var** (`func 0x04`) ~1/s reading the DB/flags that hold the **potentiometer** values and
  light status. Role: operator monitoring.
- **CPU 410 ↔ ET 200SP `<ET200SP_IP>`:** PROFINET IO cyclic RT (if the ET 200SP is on the mirrored
  switch) — not S7comm; appears in the protocol survey only.
- **Background:** ARP, Siemens LLDP, PROFINET DCP, possibly NTP/SNMP.

---

## 3. Refined tables (student worksheet)

Pre-filled cells are shown in *(italics)*; students complete the rest.

### T1 — SPAN Configuration Record  *(= W2.1)*

| Field | Value |
|---|---|
| Switch (model / mgmt IP) | *(SCALANCE XC208G / `<XC208_MGMT_IP>`)* |
| Mirror source port(s) | *(CPU 410 port)* |
| Mirror destination port | *(spare port with USB capture NIC)* |
| Direction (RX / TX / both) | both |
| Config change approved by | |
| Rollback baseline file | |
| Packet flow verified (Y/N, how) | |

### T2 — Flow Snapshot  *(merges W2.2 + W2.6)*

One row per observed flow. Roles pre-filled from the architecture; students confirm, add rows,
and judge the last column.

| Src host → Dst host | Protocol | Port | Function types seen | Operational purpose | Expected per architecture? (Y/N) |
|---|---|---|---|---|---|
| *(HMI/EWS → CPU 410)* | *(S7comm)* | *(102)* | | *(operator monitoring)* | |
| *(CPU 410 ↔ ET 200SP)* | | | | *(I/O cycle)* | |
| | | | | | |
| | | | | | |

### T3 — Baseline vs Anomaly  *(reframes W2.4 — the keystone)*

Fill the "normal" column from the pre-injection baseline, then the "anomalous" column once the
attack runs. One axis per row; the evidence column is a frame range or a display filter.

| Observation axis | Normal (baseline) | Anomalous (what changed) | Evidence (frame # / filter) |
|---|---|---|---|
| Who writes to the CPU | | | |
| Write frequency / cadence | | | |
| S7comm function codes used | | | |
| Memory area / values written | | | |
| New node on the segment | | | |

### T4 — S7comm Packet Dissection  *(= W2.3)*

3–5 representative S7comm packets: at least one read/poll, the malicious write, a
connection/setup, and (if present) a diagnostic.

| Frame # | Src → Dst | S7 service (ROSCTR / func) | Category (read / write-control / setup / diag) | Target (area, DB/addr) | Value / payload |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

### T5 — Security Assessment, anchored to the attack  *(merges W2.5 + W2.7)*

| S7comm security property | Reality (plain S7comm) | How the attack used it | Realistic control in this lab |
|---|---|---|---|
| Authentication | | | |
| Encryption / confidentiality | | | |
| Integrity | | | |
| Replay / source validation | | | |
| *(optional contrast: one other observed protocol)* | | | |

---

## 4. Hypothesised answer key

> For the injection in §2. Confirm all field names/values against the kit's Wireshark version
> (S2-Q3a / S2-Q27).

### T1 (expected)
Source = CPU 410 port; destination = spare port with the USB NIC; direction **both**; students
export the running config as the rollback baseline *before* adding the mirror, and verify flow by
seeing S7comm they are neither the source nor destination of.

### T2 (expected)

| Src → Dst | Protocol | Port | Function types | Purpose | Expected? |
|---|---|---|---|---|---|
| HMI/EWS → CPU 410 | S7comm (TPKT/COTP) | 102 | Setup comm, Read Var (0x04) | Operator monitoring of potentiometer/light state | **Y** |
| CPU 410 ↔ ET 200SP | PROFINET IO RT | — (0x8892) | Cyclic I/O | Controller ↔ remote I/O | **Y** |
| **Kali `<ATTACKER_IP>` → CPU 410** | **S7comm** | **102** | **Setup comm, Write Var (0x05)** | **Forcing outputs (lights)** | **N — not in the architecture** |
| broadcast | ARP / LLDP / PN-DCP | — | discovery | background | Y |

The single row with **N** is the finding. Students should reach it by deduction: a host talking
S7comm to the CPU that the architecture does not show.

### T3 (expected)

| Axis | Normal | Anomalous | Evidence |
|---|---|---|---|
| Who writes to the CPU | only the HMI/EWS (and only setpoints, if any) | a new host `<ATTACKER_IP>` writes | `s7comm.param.func==0x05` sourced from `<ATTACKER_IP>` |
| Write cadence | reads ~1/s; writes rare | a write burst / off-cadence writes | I/O Graph; `frame.time_delta` |
| Function codes | mostly Read Var (0x04) | Write Var (0x05) appears from the new host | `s7comm.param.func` |
| Area / values | reads of DB/flags; any HMI write targets a **DB (0x84)** | writes to the **output area (0x82)** forcing light bits | `s7comm.param.item.area==0x82` *(confirm field)* |
| New node | known Siemens MACs only | non-Siemens OUI on the segment | Statistics ▸ Conversations / Endpoints |

### T4 (expected, example rows)

| Frame | Src → Dst | Service | Category | Target | Value |
|---|---|---|---|---|---|
| n | EWS → CPU | ROSCTR Job, Read Var (0x04) | read/poll | DB/flags (sensor image) | potentiometer readings |
| n | CPU → EWS | ROSCTR Ack_Data | read reply | — | values returned |
| n | Kali → CPU | COTP CR + Setup communication (0xF0) | setup | — | new S7 connection |
| n | **Kali → CPU** | **ROSCTR Job, Write Var (0x05)** | **write/control** | **output area 0x82, byte.bit** | **bit(s) = 1 → lights on** |

### T5 (expected)

| Property | Reality | How the attack used it | Control in this lab |
|---|---|---|---|
| Authentication | none (plain S7comm) | any host on the segment could open a connection and write | **segmentation** so Kali can't reach the CPU; firewall rule allowing S7 only from the HMI |
| Encryption | none; values in clear | the write value (light bits) is readable in the capture | can't retrofit on the CPU → **compensating** monitoring, not encryption |
| Integrity | none | a valid-looking write forced physical outputs | **protocol-aware firewall / DPI** blocking Write-Var from non-HMI sources |
| Source validation | none | the CPU accepted writes from an unknown host | **allow-listing** HMI as the only writer; **new-node alerting** |

Honest OT point for the debrief: **you cannot "just turn on encryption" on the CPU** — so the
real controls are *segmentation, allow-listing and monitoring* that wrap the insecure protocol.

### Reflection answers (hypothesised)
1. **Fastest single tell:** *Statistics ▸ Conversations*, S7comm tab — an unknown host
   conversing with the CPU jumps out with no knowledge of S7 internals. (Runner-up filter:
   `s7comm.param.func==0x05` to isolate writes.)
2. **One control, biggest gain / least risk:** source allow-listing / segmentation so only the
   HMI can reach the CPU on TCP 102 — stops the attack without touching the protocol or the
   running process.
3. **What SPAN misses:** anything not crossing the mirrored port — encrypted payloads (not an
   issue for plain S7comm), direct-attached or same-switch-but-unmirrored links, and traffic
   lost to span oversubscription. Cover the gap with additional taps/mirrors or host-based logs.

---

## 5. To confirm before this is final
- The real injection (S2-Q12): function, target area, value, cadence, trigger. Replace §2.
- S7comm dissector field names/values in the kit's Wireshark version (S2-Q3a / Q27), especially
  the item-area filter.
- Kit IP scheme and which devices sit on the mirrored switch (S2-Q1) — fills `<…>` placeholders.
- Whether any legitimate HMI **writes** exist in the baseline (setpoints), so T3's "who writes"
  row is stated correctly.
