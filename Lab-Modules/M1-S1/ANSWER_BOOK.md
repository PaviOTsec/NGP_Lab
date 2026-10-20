# M1 Session 1 — Trainer Answer Book

**Source of truth for every table:** `TR-M1S1-rack-capture.pcapng` (SHA-256
`4b905b48d3e3477a185108ba28a89a9939a248badb0399eaac32e3ef739531fc`, 23,017 frames, 15 min).

For each workbook table, this book has:
1. **What students actually do** — the concrete steps on the kit.
2. **Teaching emphasis** — what the trainer wants them to walk away understanding.
3. **The expected answer table.**

Trainer uses this to **mark completeness, not correctness** (D11, familiarisation). A pair's
answer is "right" if their rationale is grounded in the capture or the asset cards, even if
the wording differs.

---

## P0 — The asset-placement puzzle (new Part A, D24)

### What students actually do

Each pair gets 7 asset cards and the architecture diagram (`puzzle_diagram.svg`), which
has 5 slots A–E in specific zones. For every card they:

1. Read the card's vendor, model and OUI hint.
2. In Wireshark, look at **Statistics ▸ Endpoints ▸ Ethernet** for a MAC that matches the
   card's OUI. If one exists, note its IP.
3. Open **Conversations** for that IP. See what it talks to and with which protocol. Match
   those flows to a slot on the diagram.
4. If the device is on the network but the IP doesn't match any slot on the diagram, mark
   the card **UNDOCUMENTED**.
5. If the OUI is nowhere in Endpoints *and* the card's protocol (e.g. `enip`) returns zero
   frames, mark the card **DISCARD**.
6. Fill IP, MAC and protocols on each card from the PCAP.

### Teaching emphasis

- **The asset-discovery loop.** Slot → IP → flows (what it does + who it talks to) → device.
  Students should be able to recite this chain by the debrief.
- **Absence is evidence.** The red-herring card isn't a trick; it is the lesson that
  "I filtered for it, I got zero frames" is a conclusion, not a failure.
- **Vendor OUIs are free intel.** Any pair that tries to solve the puzzle without opening
  Endpoints → Ethernet is spending double the time they should.
- **Undocumented ≠ wrong.** The sixth card is a *finding* — the "back door around the DMZ"
  that reappears in Session 3's Ukraine/Colonial case studies.

### Answer key — card to slot

| Card | → | Slot | IP | MAC | Confirming evidence from the PCAP |
|---|---|---|---|---|---|
| #01 Siemens CPU 410-5H | **A** | 192.168.1.10 | 74:fc:45:72:b1:6a | S7comm server (TCP 102, func 0x04 Read Var, ~890 req/resp) + PROFINET IO cycle (0x8001/0xC001) with ET 200SP |
| #02 Siemens SICAM A8000 | **B** | 192.168.3.12 | 00:e0:a8:f1:9d:54 | MMS client to .3.10 and .3.11; MMS server for OSS01 (one session @ t≈4.1 s) |
| #03 Siemens SIPROTEC 5 | **C** | 192.168.3.10 | dc:05:75:10:54:68 | GOOSE heartbeat to 01:0c:cd:01:00:01 (~1 s) + MMS server to RTU |
| #04 WAGO PFC200 | **D** | 192.168.4.13 | 00:30:de:73:94:a8 | Modbus/TCP server (TCP 502), FC3 reads from .20.10 |
| #05 Siemens PCS 7 OS Server | **E** | 192.168.20.10 | 00:15:5d:09:7e:05 | S7 *client* to CPU 410 + Modbus *master* to Wago + MMS *client* to RTU — only device talking to all three cells |
| #06 HMS Ewon Cosy 131 | **UNDOCUMENTED** | 192.168.4.50 | 00:03:27:4c:81:e2 | Second Modbus master on Wago (10 s poll + 2× FC6 writes @ 668 s / 671.5 s); 7× TCP SYN to 203.0.113.80:443, no answer |
| #07 Allen-Bradley ControlLogix | **DISCARD** | — | — | Zero `enip` and zero `cip` frames in Protocol Hierarchy; no `00:1d:9c` (or any Rockwell) OUI in Endpoints |

### Puzzle debrief script

- *"Hold up the discarded card."* → confirm "no CIP in Hierarchy, no Rockwell OUI in
  Endpoints".
- *"Hold up the undocumented card."* → confirm "second Modbus master on Wago, unanswered
  outbound SYNs".
- *"Walk me through card #02's slot."* → confirm the pair opened Conversations for
  192.168.3.12 and saw both MMS client *and* MMS server behaviour.
- *"How many cells does the device in Slot E talk to?"* → confirm "three — it's the SCADA".

---

## W1.1 — Asset Inventory

### What students actually do

**Phase 1 — Rack tour (trainer-led, 20 min):** the trainer walks each group past the Trainer
Rack. Students write one row per asset: name, location (Kit or Rack), role (one sentence),
IP, MAC, firmware/version, and *where they got the info from* (asset card, label, workstation
screen, switch WBM).

**Phase 2 — Kit walk-through (self-guided, 20 min):** at their own kit, students physically
identify each device, note the label details and the pre-filled parameter sheet addresses,
and add the kit rows. Fast finishers verify a MAC by opening the kit switch's web UI.

### Teaching emphasis

- **Every asset has a job in the process.** The CPU 410 doesn't just "exist on the network" —
  it runs the mixer. Make them say what each thing *does*.
- **Where facts come from matters.** The "Source of info" column separates observation (the
  label says CPU 410-5H) from assumption (the drawing calls it CPU 410). Students should
  distinguish the two for the rest of their career.
- **The DMZ exists for a reason.** Introduce it as the one-way-glass between IT and OT.

### Expected answer (Trainer Rack, DMZ ↓)

| # | Asset / model | Location | Role | IP | MAC | FW / version | Source |
|---|---|---|---|---|---|---|---|
| 1 | SCALANCE XC416-8 (SW-DMZ) | Rack / DMZ | DMZ switch | 10.1.20.30 | 74:fc:45:b2:3e:ce | SCALANCE XC400NG | WBM login page |
| 2 | DMZH2_EPO (Trellix ePO) | Rack / DMZ | Endpoint protection management | 10.1.20.11 | 00:15:5d:dc:59:06 | Trellix ePO 5.x | Asset card |
| 3 | DMZH2_ADWSUS | Rack / DMZ | Windows patch distribution (WSUS) | 10.1.20.12 | 00:15:5d:dc:59:08 | WS2022 + WSUS 10 | Asset card / server screen |
| 4 | DMZH1_LogServer | Rack / DMZ | Central log collection | 10.1.20.13 | 00:15:5d:09:90:01 | WS2022 + Splunk UF | Asset card |
| 5 | DMZH1_MSSQL | Rack / DMZ | SQL back-end (ePO DB) | 10.1.20.14 | 00:15:5d:09:90:07 | MS SQL Server 2022 | Asset card |
| 6 | DMZH1_SIEM (Splunk) | Rack / DMZ | SIEM | 10.1.20.15 | 00:15:5d:09:90:04 | Splunk Ent 9.x | Splunk web |
| 7 | DMZH2_SinemaRC | Rack / DMZ | Vendor remote-access server | 10.1.20.16 | 00:15:5d:dc:59:0c | SINEMA RC V3.2 | SRC login |
| 8 | DMZH2_DC | Rack / DMZ | Domain controller & DNS (np.local) | 10.1.20.17 | 00:15:5d:dc:59:03 | WS2022 AD DS | Asset card |
| 9 | DMZBM_SSM | Rack / DMZ | OT security monitor (SINEC Security Monitor) | 10.1.20.18 | 30:3e:a7:47:b4:51 | SSM V3 | SSM web |
| 10 | DMZBM_SSMSensor | Rack / DMZ | SSM passive sensor | 10.1.20.19 | 30:3e:a7:47:b4:5a | SSM Sensor V3 | Asset card |
| 11 | DMZH1_SinecINS | Rack / DMZ | Infrastructure services (NTP, syslog) | 10.1.20.21 | 00:15:5d:09:90:0a | SINEC INS V1.0 | SINEC INS web |
| 12 | SCALANCE XC208G (SW-Ops) | Rack / L3 | Operations switch | 192.168.30.30 | 74:fc:45:b8:27:c8 | SCALANCE XC200 | WBM |
| 13 | L3H1_Historian | Rack / L3 | Process historian (bare metal) | 192.168.30.10 | 40:5b:7f:3b:c2:01 | PI Historian / WS22 | Asset card |
| 14 | DMZH2_MaintServer | Rack / L3 | Maintenance server; hosts SINEC NMS | 192.168.30.11 | 00:15:5d:dc:59:09 | SINEC NMS V3.0 | NMS web |
| 15 | SCALANCE SW (SW-L2, .50) | Rack / L2 | System network switch | 192.168.20.50 | 74:fc:45:b8:28:b8 | SCALANCE | WBM |
| 16 | SCALANCE WAM763-1 (WAP) | Rack / L2 | Wireless AP (trainee kits) | 192.168.20.30 | 74:fc:45:b5:a0:b0 | FW V03.02.00 | WBM |
| 17 | L2H1_OSS01 (PCS 7 OS server) | Rack / L2 | SCADA server for all three processes | 192.168.20.10 | 00:15:5d:09:7e:05 | PCS 7 V9.1 | ES screen |
| 18 | L2H1_ES01 (Engineering Station) | Rack / L2 | PCS 7 engineering (TIA / PCS 7) | 192.168.20.11 | 00:15:5d:09:7e:01 | PCS 7 V9.1 / TIA | Asset card |
| 19 | L2BM_B&R (Veeam) | Rack / L2 | Backup & restore platform (mgmt only) | 192.168.20.12 | — | Veeam B&R 12 | Asset card |
| 20 | OT Firewall (SCALANCE SC646-2C) | Rack / L1-L2 boundary | OT firewall (L2 ↔ L1 cells) | 192.168.20.254 / .1.254 / .3.254 / .4.254 | 74:fc:45:ba:9b:1c | SCALANCE S600 | WBM |
| 21 | SW-PCS (level1switch1) | Rack / L1 PCS | PCS cell switch | 192.168.1.30 | 74:fc:45:b6:4a:bd | SCALANCE | Asset card |
| 22 | CPU 410-5H PLC | Rack / L1 PCS | Controller for the pharma CSTR | 192.168.1.10 | 74:fc:45:72:b1:6a | PCS 7 CPU 410-5H | Device label |
| 23 | ET 200SP HA I/O | Rack / L1 PCS | Remote I/O for the CSTR | 192.168.1.11 | 74:fc:45:6f:4d:a7 | ET 200SP HA | Device label |
| 24 | SW-SAS (level1switch3) | Rack / L1 SAS | SAS cell switch | 192.168.3.30 | — | SCALANCE | Asset card |
| 25 | SIPROTEC 5 Breaker IED 1 | Rack / L1 SAS | Line protection relay | 192.168.3.10 | dc:05:75:10:54:68 | SIPROTEC 5 | Device label |
| 26 | SIPROTEC 5 Breaker IED 2 | Rack / L1 SAS | Line protection relay | 192.168.3.11 | dc:05:75:10:54:69 | SIPROTEC 5 | Device label |
| 27 | SICAM A8000 RTU | Rack / L1 SAS | Substation gateway / RTU | 192.168.3.12 | 00:e0:a8:f1:9d:54 | SICAM A8000 CP | Device label |
| 28 | WAGO PFC PLC | Rack / L1 Power Gen | Controller for the power generation cell | 192.168.4.13 | 00:30:de:73:94:a8 | WAGO PFC | Device label |
| 29 | **SIS: CPU 410F + IO (SIL3)** | Rack / L1 SIS **(out of scope)** | Safety for the CSTR | 192.168.2.10/.11 | — | — | Asset card only — do not scan |
| 30 | Trainee Kit — CPU 410 | Kit | Kit controller (CSTR mimic) | 192.168.10.10 | per kit | PCS 7 CPU 410 | Device label |
| 31 | Trainee Kit — ET 200SP I/O | Kit | Kit I/O | 192.168.10.11 | per kit | ET 200SP | Device label |
| 32 | Trainee Kit — SCALANCE XC208G | Kit | Kit switch | 192.168.110.30 | per kit | SCALANCE XC200 | WBM |
| 33 | Trainee Kit — SC646-2C firewall | Kit | Kit firewall | (per kit) | per kit | SCALANCE S600 | WBM |
| 34 | Trainee Kit — Operator/ES workstation (VM) | Kit | Kit HMI / engineering (VM) | 192.168.110.10 | per kit | WS2022 + PCS 7 | OS login |
| 35 | Trainee Kit — "Hacker" (VM) | Kit | S3+ attacker VM (dormant for S1) | (WAN per kit) | per kit | Kali / Win | VM label |

> **Scoring note.** 25 rows for the rack (DMZ↓) is the minimum. Pairs who find 20+ and name
> the function get full marks for W1.1. SIS gets a row with "out of scope" in every field.

---

## W1.2 — Purdue / Zone Mapping

### What students actually do

For every row in W1.1, add Purdue level (0–5), zone, connected interfaces (segment-side),
network segment (CIDR), and a **placement rationale that cites evidence** — a label, a flow
in W1.4, or an asset-card entry. Rationale lines like *"it's a controller so it's L1"* don't
count; *"it runs ladder logic and the PCAP shows it exchanging PROFINET I/O with ET 200SP"*
does.

### Teaching emphasis

- **Purdue is about function, not where the box sits.** The OSS01 server lives on a rack in
  the DMZ cabinet physically, but it's **Level 2** because its job is operator supervision.
- **Zone/segment is about trust.** Two assets in the same subnet share the same trust level
  by default; crossing a subnet means crossing a firewall rule.
- **Island-mode SIS.** A placement of "L1-SIS, isolated zone" with the rationale "no SIS
  traffic appears in the PCAP" is the *correct* Session-1 reading.

### Expected answer

| Asset | Purdue | Zone | Connected interfaces | Segment | Rationale (evidence) |
|---|---|---|---|---|---|
| CPU 410 (PCS 7) | **L1** | Pharma Control | PCS switch Gi0/x | 192.168.1.0/24 | PCAP: PROFINET IO 0x8001/0xC001 with ET 200SP (frames 1+); S7comm Read Var replies to OSS01 |
| ET 200SP HA | **L1** (lower edge) | Pharma Control | PCS switch | 192.168.1.0/24 | PCAP: PROFINET input frames (0xC001) to CPU 410 |
| PCS switch (level1switch1) | L1/L2 infra | Pharma Control | PCS cell | 192.168.1.0/24 | OT-FW LLDP neighbour (asset card) |
| CPU 410F + IO (SIS) | **L1-SIS** | SIS island | SIS switch | 192.168.2.0/24 | **No 192.168.2.* traffic in the PCAP → confirms island mode** |
| SICAM A8000 RTU | **L1** (gateway) | Power Control / SAS | SAS switch | 192.168.3.0/24 | PCAP: IEC 61850 MMS as client to IED1/IED2; as MMS server to OSS01 |
| SIPROTEC 5 IED1 | **L1** | Power Control / SAS | SAS switch | 192.168.3.0/24 | PCAP: GOOSE publisher + MMS server to RTU |
| SIPROTEC 5 IED2 | **L1** | Power Control / SAS | SAS switch | 192.168.3.0/24 | PCAP: GOOSE publisher + MMS server to RTU, breaker-event burst ~min 9 |
| WAGO PFC PLC | **L1** | Power Generation | Wago link | 192.168.4.0/24 | PCAP: Modbus/TCP server, FC3 reads from OSS01 |
| OT Firewall (SC646) | L1/L2 boundary | — | VLAN1=PCS/SAS/L2 ; VLAN2=SIS/Wago | multiple | Routes L2 ↔ L1; four IPs (asset card) |
| L2 switch (.50) | L2 infra | System Network | L2 | 192.168.20.0/24 | Asset card; LLDP neighbour to FW-South eth1/6 |
| L2H1_OSS01 (PCS 7 OS server) | **L2** | System Network | L2 | 192.168.20.0/24 | PCAP: S7 Read Var to CPU 410; MMS client to RTU; Modbus master to Wago |
| L2H1_ES01 (Engineering Station) | **L2** (engineering sub-level) | System Network | L2 | 192.168.20.0/24 | PCAP: brief S7 session + PROFINET DCP Identify.All |
| L2BM_B&R (Veeam) | L2 (backup) | System Network | L2 mgmt | 192.168.20.0/24 | Not in the PCAP — asset card only |
| SCALANCE WAM763-1 (WAP) | L2 infra | System Network | L2 | 192.168.20.0/24 | Asset card; LLDP neighbour visible to L2 switch |
| L3H1_Historian | **L3** | Ops Management | Ops switch | 192.168.30.0/24 | PCAP: NTP to SINEC INS; functionally a historian (asset card). *(No app-level flow in this capture window — a Session-2 noticeable gap.)* |
| DMZH2_MaintServer / SINEC NMS | **L3** | Ops Management | Ops switch | 192.168.30.0/24 | PCAP: SNMP polling to SW-DMZ / SW-Ops / SW-L2 |
| Ops switch (SW-Ops) | L3 infra | Ops Management | Ops | 192.168.30.0/24 | PCAP: SNMP-poll target |
| FW-South (PA-440) | L3/DMZ/L2 boundary | — | eth1/3 L3, eth1/4 DMZ, eth1/6 L2 | multiple | Asset card; routing visible via gateway MACs in PCAP |
| DMZH2_DC | **L3.5 / DMZ** | DMZ | DMZ | 10.1.20.0/24 | PCAP: DNS replies to L2/DMZ clients |
| DMZH2_ADWSUS | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card (not in capture) |
| DMZH1_LogServer | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card (not in capture) |
| DMZH1_MSSQL | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card |
| DMZH1_SIEM | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card |
| DMZH2_SinemaRC | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card — contrasts with the planted "undocumented" gateway in W1.5 |
| DMZH2_EPO | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card |
| DMZH1_SinecINS | DMZ | DMZ | DMZ | 10.1.20.0/24 | PCAP: NTP server (every DMZ/L3/L2 host → .21 UDP 123) |
| DMZBM_SSM / SSMSensor | DMZ | DMZ | DMZ | 10.1.20.0/24 | Asset card |
| SW-DMZ | DMZ infra | DMZ | DMZ | 10.1.20.0/24 | PCAP: SNMP-poll target |

> **Common mistakes to flag during floor-walk:**
> - Historian placed at L4 (it's L3 — operations management).
> - OSS01 placed at L3 (it's L2 — process supervision; L3 is historian/MES).
> - RTU placed at L2 ("it has an IP") (it's L1 — process-level device).
> - SIS placed at L1 **without** the island qualifier (lose the key teaching point).

---

## W1.3 — AI Challenge Log (Purdue / Zone)

### What students actually do

Each pair picks **two** of their W1.2 placements and runs them through the AI chat with the
devil's-advocate prompt from the workbook. They record the AI's strongest counter-argument,
the specific capture or asset-card evidence they used to defend or correct, and whether they
kept or changed their original placement.

### Teaching emphasis

- **AI gives a plausible challenge, not a correct one.** The pair must do the work of
  checking.
- **Evidence beats argument.** A row that says "I kept my placement because I'm right" is a
  failed row.
- **Writing down why you were right is as important as being right.**

### Expected answer — exemplars (showing the *kinds* of challenge and how to resolve them)

| Placement challenged | AI counter-argument (likely) | Student evidence | Outcome |
|---|---|---|---|
| OSS01 at L2 | "It's a Windows server with AD-style name — belongs at L3 (operations)" | PCAP: OSS01 opens S7 cyclic reads to CPU 410 and Modbus to Wago — those are supervisory functions on the control bus, not operations reporting | **Kept at L2** |
| SICAM A8000 RTU at L1 | "RTU is a gateway, so it's L2 by function" | PCAP: RTU acts as **MMS client** to IEDs (reads breaker + measurement data) and **MMS server** to OSS01 — it's the SAS cell's substation controller, which is L1 by Purdue | **Kept at L1 (gateway subclass)** |
| CPU 410 at L1 | "CPU 410 is a 'PC-level' PLC and may belong at L2" | Device label says PCS 7 CPU 410-5H + the PCAP shows PROFINET IO cycles with ET 200SP (L1 function) | **Kept at L1** |
| Historian at L4 | "Historian is business data, so it's L4/Enterprise" | Asset card: it's bare metal in the ops VLAN (192.168.30.x). PCAP: on 192.168.30.0/24 segment. Operations historians are L3 by Purdue | **Moved from L4 to L3** (if the pair had placed it at L4) |
| SIS at L1 (no island qualifier) | "It should be L1 like the other controllers" | PCAP: **no traffic to or from 192.168.2.0/24** anywhere in the capture — island-mode isolation is observable from the *absence* of flows | **Corrected to L1-SIS, isolated zone** |

> Trainer: accept any two rows with evidence. Reject rows where the "evidence" is restated
> opinion.

---

## W1.4 — Communication Flow Matrix

### What students actually do

With the PCAP open:
1. `Statistics ▸ Protocol Hierarchy` — list the protocols that appear > 1 %.
2. `Statistics ▸ Conversations` → the **TCP** tab, sort by Packets desc. Then the **UDP**
   tab. Then the **Ethernet** tab for the non-IP protocols (GOOSE, PROFINET IO, LLDP, ARP).
3. For each significant flow, fill one row: source (IP + role), destination, protocol, port,
   direction, frequency / period, operational purpose.
4. Use `Statistics ▸ I/O Graph` to spot cyclic traffic and read off the period
   (`frame.time_delta_displayed`).

### Teaching emphasis

- **Protocol tells you what the flow is for.** PROFINET IO ⇒ cyclic field data. S7comm ⇒
  controller logic access. MMS ⇒ IEC 61850 power/substation. Modbus ⇒ simple poll/write.
- **Period matters.** PROFINET at 128 ms is control. S7 cyclic at 1 s is supervisory.
  NTP at 64 s is housekeeping.
- **Who initiates matters.** OSS01 is the Modbus *client*, Wago the server. In S7, OSS01 is
  the client, CPU 410 the server.
- **A missing flow is a finding too.** No OSC↔anything in the capture — teaches that an
  unmanaged switch can't be SPANned, so terminal traffic is invisible from this vantage.

### Expected answer

| # | Source (IP · role) | Destination | Protocol | Port(s) | Direction | Frequency / period | Purpose |
|---|---|---|---|---|---|---|---|
| 1 | 192.168.1.10 CPU 410 ↔ 192.168.1.11 ET 200SP | ↔ | PROFINET IO RT (0x8892) | — (Ethertype) | bidirectional | **128 ms cyclic** | Process I/O of the CSTR cell (outputs → ET, inputs → CPU) |
| 2 | 192.168.20.10 OSS01 → 192.168.1.10 CPU 410 | → | S7comm over ISO-on-TCP | TCP 102 | OSS→CPU | **~1 s cyclic** (Read Var func 0x04, 890 req/resp) | WinCC process-image refresh for the CSTR HMI |
| 3 | 192.168.20.11 ES01 → 192.168.1.10 CPU 410 | → | S7comm + PROFINET DCP Identify.All | TCP 102 + 0x8892 | ES→CPU, ES→multicast | One session @ 372 s (4 DB reads) | Engineering workstation "watch table" + "accessible devices" scan |
| 4 | 192.168.3.12 RTU → 192.168.3.10, .11 IEDs | → | IEC 61850 MMS | TCP 102 | RTU→IED | Session + reads, intg 10 s | RTU reads breaker position (XCBR1.Pos) and measurements (MMXU1) from both IEDs |
| 5 | 192.168.3.10, .11 IEDs | multicast 01:0c:cd:01:00:0x | IEC 61850 GOOSE (0x88B8) | — (Ethertype) | pub→multicast | **~1 s heartbeat** + burst (~min 9) | Breaker status GOOSE; the burst = IED2 publishing a state change |
| 6 | 192.168.20.10 OSS01 → 192.168.3.12 RTU | → | IEC 61850 MMS | TCP 102 | OSS→RTU | One session @ 4.1 s | SCADA client reads substation data from the RTU gateway |
| 7 | 192.168.20.10 OSS01 → 192.168.4.13 Wago | → | Modbus/TCP | TCP 502 | OSS→Wago | **~1 s cyclic** (FC3 reads, 896 req/resp) | WinCC polling boiler/turbine/generator metrics for the power-gen HMI |
| 8 | **192.168.4.50 (undocumented) → 192.168.4.13 Wago** | → | **Modbus/TCP** | TCP 502 | gateway→Wago | **~10 s cyclic** + **2 writes (FC6) at t=668 s and 671.5 s** | **Second Modbus master; see W1.5** |
| 9 | **192.168.4.50 → 203.0.113.80** | → | TCP SYNs to port 443 | TCP 443 | gateway→internet | 7 SYNs across the capture, **all unanswered** | Device expects an outbound internet path (own uplink?) |
| 10 | DMZH2_MaintServer (192.168.30.11) → SW-DMZ / SW-Ops / SW-L2 | → | SNMPv2c (GetBulkRequest / GetResponse) | UDP 161 | NMS→switch | ~every 30 s | SINEC NMS polling the SCALANCE switches |
| 11 | Many hosts → 10.1.20.21 (SINEC INS) | → | NTP v3/v4 | UDP 123 | client→NTP | 64 s (Windows) / 1024 s (SCALANCE) | Time sync |
| 12 | L2 + DMZ Windows hosts → 10.1.20.17 (DC) | → | DNS A queries | UDP 53 | client→DC | On demand (~45 s intervals) | Name resolution |
| 13 | Each segment | — | ARP | — | — | Occasional | Address resolution per segment |
| 14 | CPU 410, ET 200SP, SW-PCS | multicast 01:80:c2:00:00:0e | LLDP (0x88CC) | — (Ethertype) | pub→multicast | 5 s | Neighbour discovery |
| — | **Historian (192.168.30.10)** | — | **NTP only in this window** | UDP 123 | historian→NTP | 1024 s | Historian is online but **no process-data flow is visible in this 15-min window** (a Session-2 teaching hook) |
| — | **Anything ↔ SIS (192.168.2.0/24)** | — | **nothing** | — | — | — | Island-mode isolation (confirms reflection question) |

> Expect 12–16 rows filled by a competent pair. Rows 1–9 are the "must have" ones; the IT
> rows (10–14) often come up as "I saw them but didn't record them" — the trainer prompts.

---

## W1.5 — Unidentified Asset Finding

### What students actually do

Hunt the one asset in the capture that isn't on any card:

1. `Statistics ▸ Endpoints ▸ IPv4` — sort by packets, look at vendor OUIs on the Ethernet
   tab. Compare the IP list to W1.1.
2. Spot the IP that **doesn't appear in W1.1**.
3. Filter `ip.addr == 192.168.4.50` — look at the protocols and peers.
4. Note the vendor (OUI resolves to **HMS Industrial Networks**).
5. Note *two* odd things: it's a second Modbus master on the Wago, and it has unanswered
   SYNs to a public address.
6. Record the row.

### Teaching emphasis

- **Any device whose IP you can't trace to an asset card is a finding, even if it looks
  harmless.**
- **OUIs are free intelligence.** Wireshark resolves them without any special tool.
- **Suspicion signals.** Two Modbus masters on the same device, outbound-to-internet SYNs
  from a lab-only segment, and no asset-card trace — any one of these should raise an
  eyebrow; all three together is a loud alarm.
- **Confirming evidence requires leaving the chair.** Physical check of the cabinet, vendor
  contract, switch MAC-table lookup.

### Expected answer

| Attribute | Observation |
|---|---|
| **IP address** | 192.168.4.50 |
| **MAC address** | 00:03:27:4c:81:e2 |
| **OUI vendor** | HMS Industrial Networks (resolves in Wireshark's Endpoints → Ethernet tab) |
| **Protocols seen** | Modbus/TCP (FC3 polls + FC6 writes); unanswered TCP SYNs to port 443 |
| **Peers (who it talks to)** | 192.168.4.13 WAGO PFC PLC (Modbus master role); 203.0.113.80 (outbound, no reply) |
| **Likely device type** | Industrial remote-access router / cellular VPN gateway |
| **Likely Purdue level & zone** | L1 physically; **functionally an unauthorised L5 bridge** (it expects to reach the internet directly) |
| **Why it looks suspicious** | 1) Second Modbus master on the Wago, with a different polling cadence (10 s vs OSS01's 1 s). 2) Makes *write* requests (FC6) at t=668 s and 671.5 s. 3) Sends unanswered TCP SYNs to a public address — expects its own internet path. 4) **Not on any asset card.** |
| **Confirming evidence needed** | Physical check of the Power-Gen cabinet; vendor contract / change ticket; MAC-table lookup on the L1 switch to find the port; firewall logs showing the dropped outbound traffic |
| **Why this matters** | A back door around the DMZ and SINEMA RC — this is exactly the class of pathway that led to several real-world OT incidents (sets up Module 1 Session 3) |

---

## W1.6 — Asset Criticality Ranking (validated)

### What students actually do

1. Prompt the AI with the workbook text, pasting the W1.1 asset list and the W1.4 flow
   matrix.
2. Record the AI's ranking verbatim.
3. **Verify every claim** against the PCAP. At least one of the AI's dependencies will be
   wrong.
4. Produce the corrected ranking in W1.6, noting the AI error (which asset, what the AI
   claimed, what the PCAP shows instead).

### Teaching emphasis

- **"Critical" in OT = loss would stop or endanger the process.** Not "most data on the
  network", not "most expensive".
- **An AI can't know what a device does from an IP list — it will guess.** The guesses are
  often confidently wrong.
- **The PCAP is cheap ground truth** for dependency claims.

### Expected answer — validated ranking

(Rank, Trainer Rack scope. Pairs may order 3 and 4 differently if they argue well.)

| Rank | Asset | Consequence if lost | Key dependencies (evidence-checked) | AI error corrected? |
|---|---|---|---|---|
| 1 | **CPU 410 (PCS 7)** | Pharma CSTR process stops; dosing, temp control, agitator all lost | PROFINET cycle with ET 200SP (frames 1+). Loses it → no I/O → process safed by SIS | — |
| 2 | **CPU 410F (SIS)** | Loss of safety function — process must be stopped | None observable (island mode) — card-based | — |
| 3 | **SICAM A8000 RTU** | Substation gateway for the Power-Gen cell — SCADA blind to breakers/measurements | PCAP: MMS client to IED1/IED2, MMS server to OSS01 | — |
| 4 | **IED1 / IED2** | Breaker protection lost; grid stability at risk | PCAP: GOOSE heartbeats + MMS reports | — |
| 5 | **WAGO PFC PLC** | Power-generation cell stops | PCAP: Modbus server for OSS01 polling | — |
| 6 | **ET 200SP** | No field I/O for the CSTR | PCAP: PROFINET inputs to CPU 410 | — |
| 7 | **OT Firewall (SC646)** | L1 cells unreachable from L2; HMI blind, but process keeps running on its own control loops | PCAP: visible as gateway MAC on routed flows | — |
| 8 | **OSS01 (PCS 7 OS server)** | HMI blind for all three processes; **control continues at L1** | PCAP: client in S7/Modbus/MMS flows | — |
| 9 | **ES01** | Lose ability to download new logic or run diagnostics | PCAP: one brief session only | — |
| 10 | Everything else (DMZ servers, Historian, NMS, …) | Monitoring / management loss; process unaffected | PCAP: no control-path dependency | — |

### Likely AI errors (students must catch at least one)

| AI claim (typical) | What the PCAP shows | Correction |
|---|---|---|
| "**L3 Historian** is critical — needed to run the process" | 192.168.30.10 has NTP traffic only; no OPC UA / S7 / MMS to it; no flow from CPU 410 to it | Historian is **not** in the control path — rank it low |
| "**OS clients talk to the CPU 410 directly**" | No 192.168.21.x → 192.168.1.10 traffic. (OSC terminals aren't in this capture — unmanaged switch — but even if they were, PCS 7 OS clients talk only to the OS server) | OS clients → OS server only; OS server → CPU |
| "**Domain controller / AD is required for control**" | Controller flows have no DC dependency; S7/PROFINET work without AD | DC loss affects logins / name resolution, not control |
| "**The RTU is polled by the PLC**" | No 192.168.1.10 → 192.168.3.12 traffic | PLC and RTU don't talk to each other; they live in different cells |
| "**SIS and BPCS exchange safety data**" | No 192.168.2.x traffic at all | SIS is **islanded** — the only data exchange is at a physical level (hard-wired trips) |

> Minimum bar for W1.6 pass: **one** such claim identified and disproved with a specific
> frame # or Conversations row.

---

## Reflection questions — model answers

1. **Which asset was hardest to place on the Purdue model, and what evidence finally settled
   it?**
   Expected: the RTU (gateway function straddles L1/L2) or OSS01 (Windows server on an
   operations-looking segment but doing supervisory control). The settlement comes from the
   PCAP: *what the device does*, not where it sits.

2. **What in the capture told you the SIS island is isolated from the BPCS?**
   The *absence* of 192.168.2.0/24 traffic across every segment that would normally see it,
   including through the OT firewall. Island mode is confirmed by what you don't see.

3. **Where did the AI's reasoning break down, and what would have made its answer
   trustworthy?**
   The AI invents dependencies from asset names (Historian = critical, DC = required, etc.).
   What would fix it: giving it the *flow matrix* instead of the asset list, and asking it
   to cite one piece of evidence per claim.

---

## Marking summary (M7 preview)

| Deliverable | Pass threshold |
|---|---|
| **P0 Puzzle** | 7 of 7 cards sorted correctly (A/B/C/D/E/Undocumented/Discard) + IP + MAC + protocols on the 6 "present" cards |
| W1.1 Asset Inventory | ≥ 20 rows with role and source filled; SIS marked out-of-scope |
| W1.2 Purdue mapping | Every W1.1 row has a level + zone + rationale; SIS correctly marked island |
| W1.3 AI Challenge | 2 placements challenged, each with evidence and a clear kept/corrected outcome |
| W1.4 Comm matrix | Rows 1–9 of the expected table present; period field attempted |
| W1.5 Unidentified asset | 192.168.4.50 found with vendor OUI + at least two "suspicious" reasons |
| W1.6 Criticality | AI ranking recorded + at least one hallucinated dependency disproved with frame # |
| Evidence log | 4+ files named per convention, SHA-256 recorded |
