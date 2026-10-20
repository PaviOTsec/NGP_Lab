# M1 S1 Puzzle — the 7 cards

Each pair gets this 7-card pack and the architecture diagram
(`puzzle_diagram.svg`). Target print format: **A6 cards (105 × 148 mm), one per
side of an A4 sheet, double-cut** — 7 cards from 2 A4 sheets.

**Card anatomy** (front side; back blank for notes)

```
+---------------------------------------------+
| [VENDOR LOGO]                               |
|                                             |
|   <Vendor>  <Model>                         |
|                                             |
|   [ product photo / icon ]                  |
|                                             |
|   WHAT I DO:   __________________________   |
|                __________________________   |
|                                             |
|   IP:          __________________________   |
|   MAC:         __________________________   |
|   PROTOCOLS:   __________________________   |
|                                             |
|   GOES IN SLOT:   [  ]                      |
|   (A / B / C / D / E / Undocumented / Discard) |
|                                             |
|   Card ID: #M1S1-01                         |
+---------------------------------------------+
```

Students fill the blanks from Wireshark. The "GOES IN SLOT" line is the
puzzle: 5 cards map to the 5 slots on the diagram, 1 card is the
undocumented device (no slot, suspicious), 1 card has to be discarded
because the device isn't on this network at all.

> Trainer: pre-print blanks only. The card's vendor + model + photo is
> fixed; nothing else. The pair writes the IP/MAC/protocols/slot in by
> hand. If the Lab Console workstation is handy, they can type into
> W1.1 instead and the paper card stays a reference.

---

## Card #M1S1-01 — Siemens SIMATIC CPU 410-5H

- **Vendor:** Siemens AG
- **Model:** SIMATIC PCS 7 CPU 410-5H Process Automation (6ES7410-5HX08-0AB0)
- **Photo prompt:** PCS 7 CPU 410 rack with CP 443-1 CP
- **Hints for students (printed in a sidebar):**
  - "I'm a controller for process-automation plants."
  - "My Ethernet-side vendor OUI is `74:fc:45` (Siemens)."
- **(Trainer answer — not on the card):** Slot A, 192.168.1.10, S7comm + PROFINET IO + LLDP + DCP

## Card #M1S1-02 — Siemens SICAM A8000 CP

- **Vendor:** Siemens AG
- **Model:** SICAM A8000 Series Control Processor (CP-8050)
- **Photo prompt:** DIN-rail SICAM A8000 head module
- **Hints:**
  - "I'm a Remote Terminal Unit — the gateway between a substation and a SCADA."
  - "My OUI is `00:e0:a8` (SAT GmbH, the A8000's)."
- **(Trainer answer):** Slot B, 192.168.3.12, IEC 61850 MMS (client ↔ IEDs, server ↔ OSS01)

## Card #M1S1-03 — Siemens SIPROTEC 5 (7SL87)

- **Vendor:** Siemens Energy
- **Model:** SIPROTEC 5 Distance Protection 7SL87
- **Photo prompt:** SIPROTEC 5 front panel with keypad + display
- **Hints:**
  - "I'm a protection relay for a transmission line."
  - "My OUI is `dc:05:75` (Siemens Energy Automation)."
- **(Trainer answer):** Slot C, 192.168.3.10, IEC 61850 GOOSE publisher + MMS server to the RTU

## Card #M1S1-04 — WAGO PFC200

- **Vendor:** WAGO Kontakttechnik
- **Model:** PFC200 Controller (750-8212)
- **Photo prompt:** WAGO PFC200 DIN-rail controller
- **Hints:**
  - "I'm a compact PLC often used in energy and building control."
  - "My OUI is `00:30:de` (WAGO)."
- **(Trainer answer):** Slot D, 192.168.4.13, Modbus/TCP server

## Card #M1S1-05 — Siemens SIMATIC PCS 7 OS Server

- **Vendor:** Siemens AG
- **Model:** SIMATIC PCS 7 OS Server V9.1 (Windows Server 2022, Dell PowerEdge)
- **Photo prompt:** rack-mount server with PCS 7 OS splash on the console
- **Hints:**
  - "I'm the SCADA server — I give operators their process view."
  - "I run on a Windows VM (Hyper-V), so my OUI is `00:15:5d` (Microsoft)."
- **(Trainer answer):** Slot E, 192.168.20.10, S7comm *client* to CPU 410, Modbus *master* to Wago, MMS *client* to RTU — the only device that talks to all three cells

## Card #M1S1-06 — HMS Ewon Cosy 131

- **Vendor:** HMS Industrial Networks
- **Model:** Ewon Cosy 131 (industrial VPN router with cellular uplink)
- **Photo prompt:** Ewon Cosy small blue box with antenna + Ethernet ports
- **Hints:**
  - "I'm a vendor's remote-maintenance box. I speak Modbus/TCP downstream and VPN upstream."
  - "My OUI is `00:03:27` (HMS Industrial Networks)."
- **(Trainer answer):** **UNDOCUMENTED** — no slot on the diagram. Spotted via second Modbus master on the Wago + outbound SYNs. This is the "back door around the DMZ" moment.

## Card #M1S1-07 — Allen-Bradley ControlLogix (RED HERRING — must be discarded)

- **Vendor:** Rockwell Automation / Allen-Bradley
- **Model:** ControlLogix 1756-L85E Programmable Automation Controller with 1756-EN2T Ethernet module
- **Photo prompt:** Allen-Bradley ControlLogix 1756 rack
- **Hints:**
  - "I'm an industrial PAC. I speak **EtherNet/IP (CIP)** on TCP 44818 + UDP 2222."
  - "My OUI is `00:1d:9c` (Rockwell Automation)."
- **(Trainer answer):** **DISCARD** — this device isn't on this network. Confirming evidence:
  1. Protocol Hierarchy: zero `enip` or `cip` frames.
  2. Endpoints → Ethernet: no `00:1d:9c` (or any Rockwell) MAC prefix.
  3. The lab is a Siemens/WAGO shop; no AB kit is on any asset card.

---

## Answer sheet (trainer)

| Card | → | Slot | IP | MAC | Why the pair knows |
|---|---|---|---|---|---|
| #01 CPU 410 | → | **A** | 192.168.1.10 | 74:fc:45:72:b1:6a | S7comm server + PROFINET IO cycle with ET 200SP |
| #02 SICAM A8000 | → | **B** | 192.168.3.12 | 00:e0:a8:f1:9d:54 | MMS client to IED1/IED2 + MMS server to OSS01 |
| #03 SIPROTEC 5 | → | **C** | 192.168.3.10 | dc:05:75:10:54:68 | GOOSE publisher (01:0c:cd dst) + MMS server to RTU |
| #04 WAGO PFC200 | → | **D** | 192.168.4.13 | 00:30:de:73:94:a8 | Modbus/TCP server, FC3 reads |
| #05 PCS 7 OS Server | → | **E** | 192.168.20.10 | 00:15:5d:09:7e:05 | S7 client + Modbus master + MMS client — talks to all three cells |
| #06 Ewon Cosy 131 | → | **Undocumented** | 192.168.4.50 | 00:03:27:4c:81:e2 | Second Modbus master; unanswered TCP 443 to 203.0.113.80 |
| #07 Allen-Bradley | → | **Discard** | — | — | No CIP/EtherNet-IP in hierarchy; no Rockwell OUI in endpoints |

### Teaching moments the trainer should land in the puzzle debrief

1. **The slot gave you the IP; the IP gave you the flows; the flows told you the device.**
   This is the whole method of OT asset discovery in one chain.
2. **A missing card ≠ a missing device.** Card #06 has no slot — that's a *finding*, not an error.
3. **Absence is evidence too.** Card #07 is the proof that "I can't find it" is a valid
   analytical result when it's based on *where you looked*.
4. **OUI is free intel.** Students who used the Endpoints → Ethernet tab solved cards #06
   and #07 in a minute. Students who didn't took longer.
