# Lab Activities — Preparation Tracker

Tracks how each workbook activity will be run in this lab: discussion, decisions, open
questions, and preparation progress. One section per activity; work through them one at a time.

**Status tags:** `OPEN` (needs discussion) · `PROPOSED` (suggestion, not agreed) ·
`DECIDED` (operator agreed — logged in the Decision Log) · `TODO` / `IN PROGRESS` / `DONE` (prep work)

## Status at a glance

| Module / Session | Workbook part | Planning | Prep | Dry run | Next step |
|---|---|---|---|---|---|
| M1 S1 — OT Environment & Asset Landscape | Session 1 (120 min) | Classroom plan + answer book drafted (`M1-S1/`) | **PCAP v1 built, zero malformed frames** (§1.10) | — | Operator reviews ANSWER_BOOK.md; open logistics decisions in CLASSROOM_PLAN §10 |
| M1 S2 — Traffic Capture & Protocol Deep-Dive | Session 2 | Not started | — | — | — |
| M1 S3 — Incidents Through Operational Evidence | Session 3 | Not started | — | — | — |
| M1 S4 — Threat Modelling with STRIDE | Session 4 | Not started | — | — | — |

## Sources

- Workbook: `Lab-Modules/Module_1_Workbook__Understanding_and_Assessing_OT_Environments.docx`
  (the title page says "Module 1 — Fundamentals of Operational Technology (OT)").
- Architecture drawing: `Architecture/OT_Cybersecurity_Lab_Architecture_v0.3 (1).pdf`
  (NP-ARCH-001). **This is the reference for device details and IPs in teaching material
  (D6).** Known drift against observation is listed in §1.2.
- Observed inventory: `config/inventory.yaml` (DMZ, L3, L4, L5 only; L2 and below are not
  recorded by design).
- Network visibility: `docs/NMS_ONBOARDING.md` (SINEC NMS onboarding).
- Trainee Wi-Fi: WAM763-1 AP, 8 SSIDs/VLANs so kits can reach the DMZ. Design proposed, not
  built yet. 8 SSIDs = 8 kits (D2).

## Standing constraints (apply to every activity)

- **Claude / Lab Console boundary (CLAUDE.md rule 13).** Claude and the console never touch L2
  or below: Trainer Rack controllers, IEDs, RTU, SIS, L1/L2 switches, OT firewall. Anything a
  session needs from those devices comes from the drawing (D6), the trainer or the operator.
  **Offline work on files is fine**: building or validating a synthetic PCAP on MC01 touches no
  device.
- **No Hyper-V checkpoints of lab VMs** (it voids their licences). Resetting between cohorts
  therefore cannot rely on checkpoints. This also affects the existing `training-reset`
  playbook.
- **Workbook safety rules.** No change without backup, a rollback plan and trainer approval.
  The SIS island is never scanned, written to or configured. Passive first. Stop and call the
  trainer on any anomaly. AI is a challenger, not a source of truth.
- **Class shape (D2):** ~16 students, **1 trainer**, 2 students per kit, so **8 kits**. Nothing
  in a session plan may need a second staff member; anything the trainer can't watch must be
  self-guided.

---

## 1. Module 1 — Session 1: Understanding the OT Environment and Asset Landscape

### 1.1 What the activity is for, and what it asks

**Purpose (D11):** this is the **first activity of the course**. It exists so students get
familiar with the lab's devices: what each one is, what it does, where it sits and what it
talks to. It is a guided introduction, not a test. All materials (asset cards, the tour, the
capture, the answer key) should *explain*, not just instruct.

**Duration:** 120 min. **Unit of work:** a pair per Trainee Kit (8 kits). **Scenario:** the
trainer introduces one *undocumented asset* (D9: a vendor remote-access gateway that appears
only in the capture). Pairs must identify, classify and place it from the evidence.

| Part | What happens | Led by | Output |
|---|---|---|---|
| Pre-flight | Kit healthy, Kit Parameter Sheet filled, Wireshark opens, shared PCAP received, asset cards received, AI access, evidence folder created | Pair (trainer supplies values/files) | Ticked checklist |
| A — Asset identification | Trainer rack tour covering **everything DMZ and below** (D10), then the pair walks through its own kit | Trainer, then pair | W1.1 Asset Inventory |
| B — Purdue / zone mapping | Map every asset to a Purdue level 0–5 and a zone/VLAN; AI challenges 2 placements | Pair | W1.2 Purdue/Zone Mapping, W1.3 AI Challenge Log |
| C — Traffic & comms matrix | Shared rack PCAP (**synthetic, scripted, authentic packets — D4, D7**) analysed in Wireshark | Pair | W1.4 Communication Flow Matrix, W1.5 Unidentified Asset Finding |
| D — Criticality ranking | AI ranks assets; the pair finds ≥1 hallucinated dependency, disproves it with the PCAP and corrects the ranking | Pair | W1.6 Validated Criticality Ranking |
| Close | Evidence named `M1-W1-<KIT_ID>-<step>-<desc>.<ext>`, SHA-256 hashed and logged; reflection questions; trainer sign-off | Pair, then trainer | Evidence Log, sign-off |

### 1.2 Trainer Rack asset catalogue — DMZ and below (D10)

IPs came from the drawing (D6). **D12 then decided that the lab as it really is wins** wherever
the drawing and observation disagree. The "Drift" notes below are therefore resolved in favour
of the observed value. The authoritative per-device values (IP, real MAC, domain membership)
now live in the PCAP spec (`tools/lab-pcap/spec/m1s1.yaml`); §1.2a explains where they come from.

**DMZ — 10.1.20.0/24**

| Asset (drawing name) | IP | Function | Drift / note |
|---|---|---|---|
| South Firewall (Palo Alto PA-440) | 10.1.20.254 / 192.168.30.254 | DMZ ↔ Operations boundary | — |
| L3 Switch (SCALANCE XC416-8) | 10.1.20.30 | DMZ switch | — |
| DMZH2_EPO | 10.1.20.11 | Endpoint-protection management (Trellix ePO) | VM is off and has no password yet |
| DMZH2_ADWSUS | 10.1.20.12 | Patch distribution (WSUS) | Second NIC is a temporary internet uplink |
| DMZH1_LogServer | 10.1.20.13 | Central log collection `?` | Windows Server 2022, domain-joined |
| DMZH1_MSSQL | 10.1.20.14 | Database server (for which apps?) `?` | — |
| DMZH1_SIEM | 10.1.20.15 | SIEM (Splunk) | — |
| DMZH2_SINEMARC | 10.1.20.16 | Remote-access server (SINEMA Remote Connect) | — |
| DMZH2_DC | 10.1.20.17 | Domain controller / DNS (np.local) | — |
| DMZBM_SSM | 10.1.20.18 | OT security monitoring server (SINEC Security Monitor) `?` | Bare metal |
| DMZBM_SSMSensor | 10.1.20.19 | Passive monitoring sensor | Bare metal |
| DMZH2_SINECNMS | 10.1.20.20 | Network management (SINEC NMS) | **Drift:** no VM observed at .20; NMS actually runs on MaintServer 192.168.30.11 |
| DMZH2_SINECINS | 10.1.20.21 | Infrastructure services: NTP (devices sync to it), syslog/RADIUS/DHCP `?` | **Drift:** runs on DMZ-HOST-1, not DMZ-HOST-2 |

**L3 Operations Management — 192.168.30.0/24**

| Asset | IP | Function | Drift / note |
|---|---|---|---|
| Managed L2 Switch (SCALANCE XC208G) | 192.168.30.30 | Ops switch | — |
| L3H1_Historian | 192.168.30.10 | Process historian (long-term process data) | **Drift:** a bare-metal machine; "L3-Host-1" does not exist |
| DMZH2_MaintServer | 192.168.30.11 | Maintenance server; hosts SINEC NMS | — |

**L2 System network — 192.168.20.0/24 · Terminal network — 192.168.21.0/24**

| Asset | IP | Function | Drift / note |
|---|---|---|---|
| Managed L2 Switch | 192.168.20.254 (drawing) | System network switch | **Drift:** .254 is a secondary IP of the OT firewall; the switch is .50 |
| L2H1_OSS01 | 192.168.20.10 | PCS 7 OS server (gathers process data from the controllers) | — |
| L2H1_ES01 | 192.168.20.11 | Engineering station (programming, downloads, diagnostics) | — |
| L2BM_B&R | 192.168.20.12 | `?` (backup & restore server?) | Q20 |
| L2H1_OSC01 / OSC02 | 192.168.21.10 / .11 | PCS 7 OS clients (operator screens; talk only to the OS server) | Terminal network, via an unmanaged switch |
| Wireless AP (SCALANCE WAM763-1) | 192.168.20.30 | Wireless access for the trainee kits | — |
| OT Firewall (SCALANCE SC646-2C) | 192.168.1.254 / 2.254 / 3.254 / 4.254 (+ 20.254) | L2 ↔ L1 cell boundary | — |

**L1 — control networks · L0 — 3D model test bed**

| Cell | Assets (IP) | Process (L0) | Protocol (D8) |
|---|---|---|---|
| PCS — Pharma control | CPU 410 (192.168.1.10), ET 200SP (192.168.1.11), switch 192.168.1.30 | Pharmaceutical CSTR: feed dosing, agitation, temperature PID, discharge | **S7comm** |
| SIS — Pharma safety | CPU 410F (192.168.2.10), IO rack (192.168.2.11), switch 192.168.2.30 | Safety functions for the CSTR | Island: no traffic to the BPCS |
| SAS — Power control | Breaker IED 1 / 2 (SIPROTEC 5, 192.168.3.10 / .11), RTU (SICAM A8000, 192.168.3.12), switch 192.168.3.30 | Transmission / distribution: voltage, current, power, breaker positions | **IEC 61850** |
| PLC — Power generation | Wago PLC (192.168.3.13) | Fuel → boiler → turbine → generator | **Modbus/TCP** |

> **Resolved (D13):** the Power Generation cell is **192.168.4.0/24**; the Wago is
> **192.168.4.13** (gateway 192.168.4.254 on the OT firewall).
>
> **L2BM_B&R (192.168.20.12) is a Veeam backup platform** on the management interface only
> (D15). It gets an asset card, but it is not in the PCAP.

### 1.2a Real network facts used for the capture (from saved outputs; no device contacted)

Source: the read-only NMS topology outputs of 2026-10-12
(`%LOCALAPPDATA%\LabConsole\nms-onboarding\20261012-topology\`: PA-440 ARP and interface
tables, OT-FW and SW-DMZ MAC tables) and the WAP capture of 2026-10-13.

- **Routing.** The South FW (PA-440) has legs on the **DMZ** (eth1/4 10.1.20.254),
  **L3** (eth1/3 192.168.30.254) and **directly on L2** (eth1/6 **192.168.20.253**). The OT FW
  (SC646) routes L2 ↔ L1.
  - **VLAN 1** holds 192.168.1.254, 192.168.3.254 and 192.168.20.254, so the **PCS cell, SAS
    cell and L2 System network share one broadcast domain**.
  - **VLAN 2** holds 192.168.2.254 and 192.168.4.254, so the **SIS and Wago cells share one
    broadcast domain**.
- **Real MACs** for every DMZ, L3 and L2 host and the network devices come from the PA-440 ARP
  table. All Windows VMs are Hyper-V `00:15:5d:…`.
- **L1 MACs** come from the OT-FW MAC table, grouped by port:
  - Gi0/3 = PCS cell (`74:fc:45` Siemens)
  - Gi0/2 = SAS cell: SICAM A8000 `00:e0:a8` (SAT GmbH, the A8000's OUI) and two SIPROTEC 5
    `dc:05:75` (Siemens Energy Automation)
  - Gi0/6 = Wago `00:30:de` (WAGO)
  - Gi0/5 = SIS

  Within a cell, which MAC belongs to which device is inferred (for example from MAC
  production ranges). The OUIs are certain; the per-device assignment is a best guess, which is
  enough for teaching.
- **Not found in reality:** SIS IO rack MAC, switch 192.168.1.30/.3.30 MACs (aged out). The
  ePO VM (off) and the SSM sensor (.19) have no ARP entry. These get synthetic MACs with the
  right vendor prefix, marked `synthetic` in the spec.

### 1.3 Tabletop Trainee Kit (per the drawing; each kit assumed identical)

| Workbook name | Drawing | Address (drawing) |
|---|---|---|
| PCS 7 CPU 410 controller | CPU 410 | 192.168.10.10 (VLAN A, control network) |
| ET 200SP I/O modules | ET 200SP IO rack | 192.168.10.11 |
| SCALANCE SC646-2C firewall | Firewall (VLAN A, B, WAN) | ? |
| SCALANCE XC208G switch | L2 managed switch | 192.168.110.30 |
| Workstation | VM host → "Operator + Engineering Station" VM | 192.168.110.10 (VLAN B, system network) |
| *(not in the workbook)* | VM host → "Hacker" VM | WAN 192.168.210.0/24 |
| *(not in the workbook)* | USB-to-Ethernet adapter on the VM host | — |

### 1.4 Flow story for the synthetic capture

The capture must show each device *doing its job* (D10, D11). Cell protocols are fixed by D8.
**The operator was unsure about Q22, so Claude chose F6–F8 (D16)**; the operator may override.
Domain membership follows D17.

| # | Flow | Protocol / port | Pattern | Seen on |
|---|---|---|---|---|
| F1 | OSS01 → CPU 410 | S7comm, TCP 102 | Persistent connection; cyclic DB reads ~1 s (CSTR temperature, level, agitator, dosing) | L1 PCS |
| F2 | ES01 → CPU 410 | S7comm, TCP 102 + PROFINET DCP Identify | One engineering session: CPU identity, state and diagnostic buffer (SZL reads); "accessible devices" scan | L1 PCS |
| F3 | CPU 410 ↔ ET 200SP | PROFINET IO RT (0x8892) | Cyclic (I/O of a real PCS 7 cell; S7comm runs *to* the CPU, not to the I/O) | L1 PCS |
| F4 | RTU → IED 1 / IED 2 | IEC 61850 MMS, TCP 102 | RTU as station client: association, model read, reports (periodic + on change) | L1 SAS |
| F5 | IED 1, IED 2 | IEC 61850 GOOSE (0x88B8, multicast) | ~1 s heartbeat; one breaker event (~min 9) with the burst | L1 SAS |
| F6 | OSS01 → RTU | IEC 61850 MMS, TCP 102 | **Chosen:** the RTU is the substation gateway and OSS01 its SCADA client (WinCC IEC 61850 channel) | L1 SAS |
| F7 | OSS01 → Wago 192.168.4.13 | Modbus/TCP 502 | **Chosen:** OSS01 is the legitimate master; FC3/FC4 reads ~1 s (boiler pressure, turbine speed, generator MW) | L1 Wago |
| F8 | Historian → OSS01 | OPC UA, TCP 4862 (WinCC OPC UA port) | **Chosen:** the historian subscribes to OS-server tags; publish ~1 s; SecurityMode None (readable, a finding in itself) | L3 |
| F9 | OSC01/02 ↔ OSS01 | — | **Not in the capture:** the terminal network hangs off an unmanaged switch, with no SPAN. That is a capture-visibility lesson; the cards cover OSC | — |
| F10 | SINEC NMS (192.168.30.11) → SW-Ops, SW-DMZ, OT-FW | SNMPv3 authPriv, UDP 161 | Polling | at the target |
| F11 | SCALANCE / OT-FW → SINEC INS 10.1.20.21; domain members → DC | NTP / W32Time, UDP 123 | Periodic | at the client |
| F12 | Domain members (D17) ↔ DC 10.1.20.17 | DNS, Kerberos, LDAP | Background | at the client |
| F13 | Domain members → WSUS 10.1.20.12 | HTTP 8530 (SOAP) | 1–2 check-ins | at the client |
| F14 | Domain members → ePO 10.1.20.11 | TLS 443 | Agent check-ins | at the client |
| F15 | Network devices → SIEM (syslog UDP 514); LogServer → SIEM (TLS 9997) | Syslog / TLS | Continuous | at the client |
| F16 | SSM sensor → SSM server | TLS 8443 | Periodic | DMZ |
| F17 | Remote user (L5) → SINEMA RC 10.1.20.16 | OpenVPN | One session (*optional, later phase*): the *documented* remote-access path, as a contrast to the planted gateway | DMZ |
| F18 | Background | ARP, ICMP | — | each segment |
| — | **Anything ↔ SIS 192.168.2.0/24** | — | **None** — see Q25 | — |

Domain members (D17): every Windows host. That is LogServer, MSSQL, SIEM, ePO, ADWSUS, DC,
MaintServer, OSS01, ES01 (and OSC01/02). **Not members:** SINEC INS (Linux), SINEMA RC
(appliance), SSM and the SSM sensor (bare metal), the Historian (bare metal) and Veeam (bare
metal).

**Planted asset (D9) — spec (DECIDED with D9; details are Claude's)**

- **What:** an **HMS Ewon**-style remote-access router at **192.168.4.50** on the Wago cell,
  not on any asset card.
- **MAC:** `00:03:27:…`. Wireshark resolves the prefix to *HMS Industrial Networks* (the vendor
  of Ewon remote-access routers).
- **Why it looks suspicious:**
  1. It is a *second* Modbus master on the Wago, beside OSS01 (F7).
  2. It polls every 10 s, a different rhythm from the OS.
  3. At ~min 11 it makes a few **writes** (FC6/FC16) that change a setpoint.
  4. A few outbound attempts to a public address through 192.168.4.254 that **get no answer**.
     It expects an internet path of its own. No real vendor cloud names are used (D22).
  5. Low volume overall (D22).
- **What students should conclude:** an undocumented third-party remote-access device at
  Level 1, effectively a back door around the DMZ and SINEMA RC. Confirming evidence would be a
  physical check of the cabinet, the vendor contract and a switch MAC-table lookup.
- It sets up the remote-access incidents in Session 3.

**Hallucination baits (PROPOSED).** These are claims a chat AI typically makes that the capture
disproves:

1. The historian is needed for control. There is no historian → controller flow.
2. OS clients talk to the CPU 410. They talk only to OSS01.
3. The SIS exchanges data with the BPCS. There is no 192.168.2.x traffic.
4. The PCS controller polls the RTU. There is no CPU 410 ↔ RTU flow.
5. The DC or AD is required for the process to run. Controller flows don't depend on it.

### 1.5 Synthetic capture — build approach

**Decided:** scripted (D4, D7). Packets must be **authentic** (D7) and aligned with this
activity.

**Proposed method: "emulate → capture → rewrite → merge" (PROPOSED)**

1. **Generate with real protocol stacks** wherever one exists, run offline on MC01 over
   loopback or an isolated virtual network (no lab device touched):
   - S7comm: snap7 client/server
   - IEC 61850 MMS + GOOSE: libiec61850
   - Modbus/TCP: pymodbus
   - SNMPv3: pysnmp
   - NTP, syslog, HTTP, TLS: standard libraries

   Real stacks produce real handshakes, sequence numbers and payload encodings.
2. **Hand-build only where no usable stack exists**, e.g. PROFINET IO RT cyclic frames and DCP.
   The structure is simple, but every frame must dissect cleanly.
3. **Rewrite** each stream to the lab plan: IPs, per-segment MACs, and the gateway MAC when a
   flow crosses a router (a real lesson: remote IPs show up behind the firewall's MAC). Set the
   timing to the periods in §1.4.
4. **Merge** onto one timeline of ~15 min. Run the validation gate (R7). Record the SHA-256.
   Generate the answer key from the same spec.
5. **Optional:** for Windows/IT background flows (F12–F15), real traffic could be recorded on a
   DMZ VM with the built-in `pktmon`. That is a change on a lab VM, so it needs explicit
   operator approval (rule 14). Not planned unless approved.

**Capture vantage point (D18):** a **multi-point capture**, i.e. an aggregated SPAN of SW-DMZ,
SW-Ops, the L2 switch (.50) and the L1 PCS and SAS/Wago switches. **No VLAN tags** (D14).
Segments are told apart by subnet, as in reality.

- Each routed flow appears **once**, as seen on the segment named in §1.4. On that segment the
  remote end shows the routing firewall's real MAC. That is a lesson in itself.
- Real L2 adjacency is kept: ES01's PROFINET DCP reaches the PCS devices directly, because
  VLAN 1 bridges the L2 and L1 subnets.
- The SIS switch is not mirrored (workbook rule).

**Requirements**

| # | Requirement | Why |
|---|---|---|
| R1 | Every IP, MAC (with the correct vendor OUI) and hostname matches the asset cards and the real lab (D12) | W1.1 (tour) and W1.4 (PCAP) must agree |
| R2 | Every asset DMZ and below appears doing its function (§1.4) | Familiarisation (D11) and W1.4 |
| R3 | No flow to or from the SIS; the vantage point would have shown one | The reflection question about SIS isolation |
| R4 | Cyclic traffic has clear, distinct periods (ms PROFINET vs ~1 s S7/MMS/Modbus vs 10 s planted asset) | The I/O Graph and the frequency column |
| R5 | The planted asset is classifiable from OUI + protocols + peers, and its placement is arguable | W1.5 and the AI challenge |
| R6 | All five baits (§1.4) can be disproved from the capture | Part D |
| R7 | Zero malformed packets or expert errors in the kit's Wireshark version (gated with `tshark`) | Authenticity (D7) |
| R8 | One spec file + versioned script + fixed seed; the PCAP's SHA-256 is recorded | Identical every cohort; answer key from the same source |
| R9 | ~15 min of capture time, < 50 MB, opens quickly on the kit workstation VM | Usability |

### 1.6 Gaps

- **G1** — ~~Rack capture needs a manual SPAN.~~ **Resolved (D4).**
- **G2** — SIS isolation evidence: handled by design (R3 + the vantage point). Closes when the
  vantage point is agreed.
- **G3** — Answer key and rack facts: rack facts come from the drawing (D6). The answer key is
  generated from the PCAP spec. Still open: the functions marked `?` in §1.2 and the flows in
  Q22.
- **G4** — Kit discovery tools for MAC/firmware (Q9).
- **G5** — ~~AI tool.~~ **Resolved (D5).** Residual: moving text between the kit and the AI
  device (Q16).
- **G6** — Distribution and collection of files for 8 kits (Q10).
- **G7** — One trainer: the kit walk-through must be self-guided (P3).
- **G8** — Kits may share identical IPs; the per-kit Wi-Fi VLAN + NAT handles it.
- **G9** — Kit workstation baseline: Wireshark version (R7 must target it), PCAP location.
- **G10** — Reset between cohorts without VM checkpoints (Q12).
- **G11** — Workbook Part C says "live capture". Q18: with D11 (guided first session), I
  suggest the trainer simply explains that it was recorded from the rack.
- **G12** — The 120-minute budget is tight for one trainer (P3).
- **G13 (new)** — **The tour now covers DMZ and below (D10), but most DMZ/L3/L2 assets are VMs
  with nothing to point at.** Their "tour" has to be shown on screens: an OS screen, SINEC NMS
  topology, the SIEM dashboard, the SINEMA RC portal, and so on. Rich asset cards carry the
  rest. That pushes the asset-card pack to the centre of the session (D11).
- **G14 (new)** — **Wireshark is not installed on MC01.** The build machine needs it (with
  `tshark`) for the R7 gate, ideally the same version as the kit workstations.
- **G15 (new)** — **Drawing vs observed drift** (§1.2): SINEC NMS location, the SINEC INS host,
  the L2 switch IP, and the Historian being bare metal. What students see on screens during the
  tour (e.g. NMS at 192.168.30.11) will contradict cards built from the drawing (Q19).

### 1.7 Proposals for discussion (not decided)

- **P1 / P2** — superseded by D4 / D3 / D9.
- **P3 — Run-sheet draft for 1 trainer and 8 pairs.** Kits 1–4 are group 1; kits 5–8 are
  group 2.

  | Time | Trainer | Group 1 | Group 2 |
  |---|---|---|---|
  | 0:00–0:10 | Briefing, safety rules, hand out pre-filled parameter sheets and asset cards | Pre-flight | Pre-flight |
  | 0:10–0:30 | Rack tour, group 1 (physical L1/L0 + on-screen DMZ/L3/L2) | Rack tour | Self-guided kit walk-through (W1.1, kit rows) |
  | 0:30–0:50 | Rack tour, group 2 | Self-guided kit walk-through | Rack tour |
  | 0:50–1:10 | Floats; checks W1.1/W1.2 | Part B + AI challenge | Part B + AI challenge |
  | 1:10–1:45 | Floats; at ~1:15 announces "there is a device on the network nobody documented" | Part C (PCAP, W1.4, W1.5) | Part C |
  | 1:45–2:00 | Debrief: reveals the planted gateway, walks through the baits | Part D + hashing | Part D + hashing |
  | After class | Sign-off from the submitted evidence bundles | — | — |

- **P4 — Distribution through the shared clipboard.** One board item each for the PCAP, the
  asset-card pack and the parameter sheets, fetched from each kit over the DMZ. This depends on
  the Wi-Fi build; USB sticks are the fallback.
- **P5 — Kit IDs follow the Wi-Fi.** KIT01–KIT08 correspond to SSID/VLAN 101–108.
- **P6 (new) — The asset card is the main teaching object (D11).** One card per asset: photo or
  screenshot, model, IP/MAC, Purdue level and zone, *what it does in the process*, what it
  talks to and why, and "why it matters / what if it's lost". The pack doubles as the answer
  source for W1.1/W1.2 and for later sessions.

### 1.8 Open questions

| # | Question | Status |
|---|---|---|
| Q1 | Activity 1 = Session 1? | **DECIDED (D1)** |
| Q2 | Class size, students per kit, staff? | **DECIDED (D2)** |
| Q3 | Rack scope for Part A/B? | **DECIDED (D10)**: DMZ and below |
| Q4 | Undocumented asset approach? | **DECIDED (D3, D9)** |
| Q5 | Live or pre-recorded capture? | **DECIDED (D4)** |
| Q6 | Are the kits physically ready? Same IPs on every kit? Is the SC646 management IP known? Is the Hacker VM present? | OPEN |
| Q7 | What is the "interactive 3D model": the L0 physical test bed, software, or both? | OPEN |
| Q8 | AI tool and IP policy? | **DECIDED (D5)** |
| Q9 | Which discovery tools may pairs use on their kit in S1, and against which targets? | OPEN |
| Q10 | What is `<EVIDENCE_STORE>`: a per-kit share on MC01, the clipboard board, USB, or the LMS? | OPEN |
| Q11 | Rack facts source? | **DECIDED (D6)**: the drawing |
| Q12 | Kit reset between cohorts: what is the baseline, and are checkpoints allowed on kit VMs? | OPEN |
| Q13 | Trainer-side material in scope? | **Answered by D11**: yes, explanatory material (asset cards, answer key, debrief) |
| Q14 | Synthetic approach? | **DECIDED (D7)**: scripted, authentic packets |
| Q15 | Cell protocols? | **DECIDED (D8)**; remaining flows in Q22 |
| Q16 | On which device do pairs use the AI chat (own laptop/phone, or the kit workstation)? How does text move between it and the kit? | OPEN |
| Q17 | Which planted asset? | **DECIDED (D9)** |
| Q18 | Workbook "live capture" wording: suggest the trainer explains it was recorded from the rack | PROPOSED |
| Q19 | Drawing or observed values for the drift items? | **DECIDED (D12)**: the lab as it really is |
| Q20 | What is L2BM_B&R? | **DECIDED (D15)**: Veeam, management-only, not in the PCAP. Functions still marked `?` (LogServer, MSSQL, SSM, SINEC INS) are filled with Claude's realistic choices in §1.4 |
| Q21 | Wago cell subnet? | **DECIDED (D13)**: 192.168.4.0/24, Wago 192.168.4.13 |
| Q22 | F6 / F7 / F8 flows? | **DECIDED (D16)**: the operator was unsure, so Claude chose (§1.4) |
| Q23 | Domain members? | **DECIDED (D17)** |
| Q24 | VLAN tags? | **DECIDED (D14)**: none; separate subnets |
| Q25 | **DECIDED (D20)**: no SIS traffic. Original question: **SIS reality vs workbook.** The real OT-FW puts the SIS (192.168.2.0/24) on **VLAN 2 together with the Wago cell** (192.168.4.0/24), routes it (192.168.2.254), and has an any→any rule. In reality the SIS is *not* an island, and a capture on the Wago link would show SIS broadcasts (ARP/DCP). Should the S1 capture show **(a) the intended island**, with no SIS frames at all, or **(b) reality**, with SIS broadcasts leaking into the Wago capture? Recommendation: **(a) for S1** (familiarisation; matches the workbook). Keep (b) as a deliberate discovery for S4 ("what if the island assumption is removed"), and record the real gap separately for the lab owner | OPEN |
| Q26 | **DECIDED (D21)**: left out. Original question: two unidentified Hyper-V VMs on the L2 System network: **192.168.20.13** (`00:15:5d:09:7e:0d`) and **192.168.20.14** (`…:0e`), plus an unknown MAC `5c:67:83:27:38:f0` behind the L2 switch. What are they (OS-client system-bus NICs?)? Default: **left out** of the capture | OPEN |
| Q27 | Which Wireshark version is on the kit workstations? MC01 should match for the R7 gate | MC01 has 4.6.9; kit version not confirmed |
| Q28 | ~~Controller-protocol traffic source~~ | **RESOLVED**: generated by Claude after switching models (D23) — real protocol stacks (snap7, libiec61850, pymodbus) run on 127.0.0.1, no lab device touched |

### 1.9 Prep task list

| # | Task | Owner | Status |
|---|---|---|---|
| T1 | Rack facts | Operator + saved outputs | DONE (D12–D17, §1.2a) except Q25/Q26 |
| T2 | Write the PCAP spec as one machine-readable file (`tools/lab-pcap/spec/m1s1.yaml`) | Claude | IN PROGRESS |
| T3 | Install Wireshark/tshark on MC01, same version as the kits (Q27) | Operator | TODO |
| T4 | Build the generator and produce the PCAP; R7 gate run by Claude with `tshark` (D19) | Claude | IN PROGRESS (§1.10) |
| T5 | Generate the answer key (W1.1/W1.2/W1.4/W1.5/W1.6 expectations) from the spec | Claude | TODO |
| T6 | Asset-card pack, DMZ and below (P6) | Claude drafts; operator supplies photos/screens | TODO |
| T7 | Dry run: the operator works through Part C/D on the PCAP with a real AI chat and confirms the baits trigger | Operator | TODO |

### 1.10 PCAP build status

| Step | What | Status |
|---|---|---|
| B1 | Tools environment `tools/lab-pcap/.venv` (Python 3.13). Stacks: snap7 3.2.1 (S7comm), libiec61850 1.6.1 (MMS), pymodbus, asyncua (OPC UA), pysnmp, scapy. Every emulated server binds **127.0.0.1 only** | DONE |
| B2 | Spec file `tools/lab-pcap/spec/m1s1.yaml`: hosts (IP, real/inferred/synthetic MAC, segment, domain), routers, flows, timing | DONE |
| B3 | Core: TCP rebuilder (handshake, seq/ack, per-OS TTL/window), MAC/TTL view per segment, pcapng writer, Npcap loopback capture for the MMS flow (libiec61850's connect rejects a proxy relay) | DONE |
| B4 | OT flows: S7comm (snap7, cyclic + ES session), PROFINET RT (hand-built, APDU trailer correct), MMS (libiec61850 real reads), GOOSE (hand-built, dissects cleanly), Modbus (pymodbus), planted gateway (D22, with uneven polling + irregular writes + unanswered outbound SYNs) | DONE |
| B5 | IT/DMZ flows: SNMPv2c (switch polling, variable timing), NTP (per-host offsets, occasional misses), DNS (random query mix), ARP | DONE. Deferred: WSUS, TLS check-ins and syslog not yet in the capture — can add if the operator wants richer DMZ noise |
| B6 | Merge + `tshark` validation. Current: 23017 frames, 15 min, ~2.4 MB, **0 malformed**, protocol hierarchy covers pn_io / goose / mbtcp / s7comm / mms / snmp / ntp / dns / lldp / arp | DONE |
| B7 | Answer key (W1.1–W1.6 expectations) + asset-card pack | TODO |

---

## Decision Log

| ID | Date | Activity | Decision | Rationale |
|---|---|---|---|---|
| D1 | 2026-10-13 | M1 S1 | "Activity 1" = workbook Session 1 (Understanding the OT Environment and Asset Landscape) | Operator |
| D2 | 2026-10-13 | All | Class ≈ 16 students, **1 trainer**, 2 students per kit, so **8 kits** | Operator; matches the 8-SSID Wi-Fi design |
| D3 | 2026-10-13 | M1 S1 | The undocumented asset is **artificial**: it need not physically exist | Operator; no hardware changes, repeatable |
| D4 | 2026-10-13 | M1 S1 | The rack capture is **pre-recorded and synthetic**, not live | The rack can't be captured completely from one point, and a live capture changes run to run; synthetic keeps the teaching identical every cohort |
| D5 | 2026-10-13 | All | The AI tool is a normal web-based AI chat, arranged by the operator; **lab IPs may be pasted** into it | Operator; no confidentiality concern for lab addressing |
| D6 | 2026-10-13 | M1 S1 | Device details and IPs for teaching material come from the **architecture drawing** | Operator; drift vs observation listed for review (Q19) |
| D7 | 2026-10-13 | M1 S1 | The capture is generated **by script only**, but the packets must be **authentic** and aligned with this activity | Operator |
| D8 | 2026-10-13 | M1 S1 | Cell protocols: **Pharma CSTR = S7comm**, **Transmission/Distribution = IEC 61850**, **Power Generation = Modbus** | Operator |
| D9 | 2026-10-13 | M1 S1 | Planted asset = a **vendor remote-access gateway talking Modbus to the Wago PLC**; it should look suspicious | Operator (from Claude's candidates) |
| D10 | 2026-10-13 | M1 S1 | Rack scope for the tour, inventory, mapping and capture = **everything DMZ and below**, mimicking each asset's function | Operator |
| D11 | 2026-10-13 | M1 S1 | Session 1 is a **familiarisation** activity (the first of the course). Materials should explain the devices, not just instruct | Operator |
| D12 | 2026-10-13 | All | **The lab as it really is wins** over the drawing wherever they differ (refines D6) | Operator |
| D13 | 2026-10-13 | M1 S1 | The Power Generation cell is **192.168.4.0/24**; the Wago is **192.168.4.13** | Operator; matches the OT-FW config (VLAN 2, 192.168.4.254) |
| D14 | 2026-10-13 | M1 S1 | **No VLAN tags** in the capture: all segments are separate subnets, as in reality | Operator |
| D15 | 2026-10-13 | M1 S1 | L2BM_B&R is a **Veeam** platform on the management interface only, so it is **not in the PCAP** | Operator |
| D16 | 2026-10-13 | M1 S1 | Claude chooses the unknown flows (operator unsure): OSS01 = IEC 61850 client of the RTU; OSS01 = Modbus master of the Wago; Historian ← OSS01 via OPC UA | Realistic for a WinCC/PCS 7 OS server; operator may override |
| D17 | 2026-10-13 | M1 S1 | **All hosts are domain members except** Linux/Debian-based systems and bare-metal installations | Operator |
| D18 | 2026-10-13 | M1 S1 | Capture vantage point = multi-point SPAN (DMZ, L3, L2, L1 PCS, L1 SAS/Wago), no tags, each flow appears once | Follows from D14 |
| D19 | 2026-10-13 | M1 S1 | The operator installs Wireshark on MC01; Claude runs the validation with `tshark` itself. A visual check on a kit happens in the dry run (T7) | Operator / Claude |
| D20 | 2026-10-13 | M1 S1 | **No SIS traffic at all** in the PCAP: it demonstrates island mode as designed. The real VLAN 2 sharing is kept as a separate note for the lab owner and a possible S4 discussion | Operator (answers Q25) |
| D21 | 2026-10-13 | M1 S1 | The unidentified L2 hosts (192.168.20.13/.14, unknown MAC) are **left out** for now | Operator (answers Q26) |
| D22 | 2026-10-13 | M1 S1 | The planted gateway stays **simple and low-volume**: a remote-access vendor MAC prefix, a second Modbus master on the Wago with its own polling rhythm, a couple of setpoint writes, and a few unanswered outbound attempts. No dependence on any real vendor's cloud details | Operator |
| D23 | 2026-10-14 | M1 S1 | Flow traffic to be **non-uniform**: realistic jitter, occasional missed cycles, variable DNS query mix, NTP sync drift. Avoids a "metronome" look that would read as synthetic | Operator |
| D24 | 2026-10-14 | M1 S1 | Part A reshaped as an **asset-placement puzzle**: 7 cards + a diagram with 5 slots. 5 cards fit the slots; 1 is the undocumented device (no slot); 1 must be discarded because its device isn't on the network. Same puzzle for all 8 kits; students may discuss. Fuses the "undocumented asset" discovery into Part A. Materials: `puzzle_cards.md`, `puzzle_diagram.{mmd,svg,png}` | Operator |

## Changelog

- 2026-10-13: Tracker created. Read M1 Session 1 and did a first-pass mapping to the lab;
  listed gaps G1–G10, proposals P1–P4 and questions Q1–Q13.
- 2026-10-13: Logged D1–D5. Resolved G1 and G5. Added G11–G12, the synthetic-capture design,
  the run-sheet draft (P3), P5, Q14–Q18 and prep tasks.
- 2026-10-13: Logged D6–D11. Added the rack asset catalogue DMZ and below (§1.2) with drift
  notes, the flow story F1–F18, the planted-asset spec and baits (§1.4), the build method and
  vantage point (§1.5), G13–G15, P6, Q19–Q24, and reworked the task list T1–T7. Checked MC01:
  Wireshark is not installed.
- 2026-10-13: Logged D12–D19. Took real MACs and routing from the saved NMS/WAP outputs (§1.2a).
  Finalised the flows (§1.4) and the planted Ewon-style gateway at 192.168.4.50. Found the real
  SIS/Wago VLAN 2 sharing (Q25) and unknown L2 hosts (Q26). Started the PCAP build (§1.10).
- 2026-10-13: Logged D20–D22: no SIS traffic, unknown L2 hosts left out, a simple low-volume
  planted gateway. Tools environment `tools/lab-pcap/.venv` set up with snap7, libiec61850,
  pymodbus, asyncua, pysnmp and scapy; the stacks were checked to work bound to 127.0.0.1.
- 2026-10-14: PCAP v1 built end-to-end. 23017 frames, 15 minutes, 2.4 MB, **0 malformed** per
  `tshark`. Protocol hierarchy includes pn_io, goose, mbtcp, s7comm, mms (full ACSE/PRES/SES
  stack), snmp, ntp, dns, lldp, arp. D23 logged: traffic deliberately non-uniform.
- 2026-10-14: Logged D24 (asset-placement puzzle twist). Produced `puzzle_diagram.{mmd,svg,png}`
  and `puzzle_cards.md`. Updated `CLASSROOM_PLAN.md` Part A and added puzzle debrief at 0:50;
  added section P0 to `ANSWER_BOOK.md`.
