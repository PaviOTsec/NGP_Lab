# M1 Session 2 — OT Traffic Capture and Protocol Deep-Dive · Preparation Tracker

Tracks how workbook **Module 1, Session 2** will be run in this lab: discussion, decisions,
open questions and preparation progress. It covers the whole delivery: how the trainer runs it,
what students do, logistics and constraints, not just the network side.

This file sits beside the main tracker `LAB_ACTIVITIES_TRACKER.md` (M1 S1 is being prepared
there in parallel). Materials live in `M1-S2/`: refined tables + hypothesised answer key in
`M1-S2/S2_tables_and_answer_key.md`. The main tracker's **standing constraints** and **all-session decisions**
apply here too: D2 (16 students, 1 trainer, 8 kits), D5 (web AI chat, lab IPs may be pasted)
and D12 (the lab as it really is wins over the drawing). To avoid clashing with its IDs,
this file prefixes everything with `S2-`.

**Status tags:** `OPEN` (needs discussion) · `PROPOSED` (suggestion, not agreed) ·
`DECIDED` (operator agreed; see the Decision Log) · `TODO` / `IN PROGRESS` / `DONE` (prep work)

## Status at a glance

| Area | Status | Next step |
|---|---|---|
| Activity read and mapped to the lab | DONE (2026-10-14) | — |
| Kit reality (wiring, host, live traffic) | DECIDED (S2-D1 to S2-D6) | — |
| Anomaly approach | DECIDED (S2-D2): live Kali S7comm injection, no synthetic PCAP | Scope the injector (S2-Q12 to S2-Q14) |
| SPAN mechanics | RESOLVED (S2-D7): dedicated mirror port + USB capture NIC | Claude drafts the exact XC208G mirror config/removal steps (needs firmware, S2-Q3a) |
| Focus protocol | DECIDED (S2-D8): S7comm only | Claude starts the S7comm reference guide + answer key |
| Run-sheet | PROPOSED (S2-P1) | Revise to the S2-D7 wiring |
| Materials | Not started | — |
| Dry run | — | — |

## Source

Workbook `Module_1_Workbook__Understanding_and_Assessing_OT_Environments.docx`, Session 2
(pages 14–20). Kit hardware as summarised from the architecture drawing in the main tracker §1.3.

---

## 0. Kit reality (operator, 2026-10-14)

How a Trainee Kit is actually built and how Session 2 will run on it. This supersedes the
drawing-derived assumptions in §1.3 of the main tracker and resolves S2-Q1–Q3/Q5/Q8.

- **Wiring is fixed — no re-cabling (S2-D1).** Two Ethernet cables leave the kit: one **WAN**
  and one **EWS** (engineering workstation). The internal control wiring (CPU 410, ET 200SP,
  SC646, XC208G) does not change.
- **Host (S2-D4):** a **Windows** machine running **VirtualBox**. Both the engineering
  workstation and the **Kali ("Hacker")** VM run on it. The host sits on the **EWS** cable.
- **Live traffic exists (S2-D5).** Real OT traffic is on the kit; nothing is synthesised.
  **No fake PCAPs for Session 2 (S2-D2).**
- **Anomaly = live injection from the Kali VM (S2-D2).** A script/executable on Kali sends
  rogue S7comm toward the kit's CPU 410 (an attacker on the control network). This replaces the
  earlier golden-capture idea (S2-P2 withdrawn).
- **SPAN method (S2-D3):** students reconfigure the **EWS switch port as the monitor
  (SPAN destination) port** and capture the mirrored traffic on the host, then restore it.
- **Access (S2-D6):** Claude **may** work directly on the kit devices. They are currently
  arranged so they are **not reachable**; this is deliberate, not a fault. Until reachable,
  Claude's work is offline (materials, manual review, injector + answer-key design).
  *Recommend recording this kit-access grant in CLAUDE.md as an explicit rule-13 scope note,
  alongside the WAP and SC646-2C exceptions, before any kit is actually touched.*

**SPAN design — RESOLVED (S2-D7).** The EWS cable is bridged (VirtualBox) to **both** the EWS
VM and the Kali VM, so the **EWS port stays a normal access port** and Kali attacks the PLC
unhindered. The **USB-to-Ethernet adapter** (freed from Kali) is cabled to an **additional
XC208G port configured as the mirror (SPAN) destination**; Wireshark captures on it. This drops
the dependency on the fragile dual-function monitor-port behaviour.

- The additional port **must be a mirror destination** — a plain access port won't see the
  unicast S7comm (a switch doesn't flood unicast). The XC208G's dedicated-mirror-destination
  support is near-certain; confirm the exact config/removal steps from the firmware (S2-Q3a).
- **Physical setup once:** USB adapter stays cabled to the spare port. **Student task each
  session:** configure the mirror session, capture, then remove it at restore — this is the
  workbook's Part A objective, with no fragile re-cabling.
- **Suggested mirror source:** the **CPU 410 port, both directions** — captures all S7comm to
  the PLC (legitimate EWS polling + Kali's rogue traffic + replies). If the ET 200SP is on the
  same switch, PROFINET also appears (a realistic survey in Part B; deep-dive stays on S7comm).
- Kali appears as a **new node** on the control network — itself a classic anomaly signature.

**Injection (S2-D9).** The kit's physical I/O is **lights (outputs) and potentiometers
(sensor inputs)**, with **hardware reset buttons** that return the logic to its starting state.
The anomaly is an S7comm **write that drives outputs so some lights turn on** — a visible,
physical effect paired with the packet evidence. Reset between pairs/cohorts is a **button
press** (no software reset needed; S2-G13 closed). The operator will design the attack
showcase later (S2-Q12 still open for the exact function/payload/trigger).

---

## 1. What the activity asks

**Duration:** 120 min. **Unit of work:** a pair per Trainee Kit.

**Scenario:** the trainer provides **baseline traffic plus one controlled protocol anomaly**
(examples given: an unexpected write, a diagnostic request, a new communicating node, a
replayed sequence, an unusual message frequency). **The trainer picks one protocol to focus
on**; pairs are not expected to cover every protocol.

**Learning objectives:** configure and verify SPAN on the SCALANCE XC208G; capture live OT
traffic safely and classify protocols by OSI layer and Purdue level; dissect the selected
protocol (operation type, addressing, transaction IDs); assess protocol security; produce an
OT Traffic Documentation Table and a Protocol Security Summary.

| Part | What happens | Kit change? | Output |
|---|---|---|---|
| Pre-flight | SPAN pre-check with the trainer; switch config exported as a rollback baseline; capture host cabled to the monitor port; Protocol Reference Guide to hand; protocol in scope announced; approval confirmed | Export only | Ticked checklist |
| A — SPAN | Trainer demonstrates SPAN on the **Trainer Rack XC208G**. Pairs configure it on their **kit XC208G** with approval, cable Wireshark to the monitor port and verify they see traffic they are not part of | **Yes** | W2.1 SPAN Configuration Record |
| B — Capture & survey | Live capture **15–20 min**, saved as `M1-W2-<KIT_ID>-04-span-capture.pcapng`; Protocol Hierarchy | No | W2.2 Protocol Usage Matrix |
| C — Deep-dive | Filter for the selected protocol; dissect 3–5 packets (at least one read, one write/control, one diagnostic/setup); count function types; find the anomaly | No | W2.3 Packet Dissection, W2.4 Function Types & Anomaly Note |
| D — Security | Security properties of the selected protocol; compare two observed protocols; AI explains why each protocol is used (validated against the guide and the capture) | No | W2.5 Comparison, W2.6 Traffic Documentation Table, W2.7 Security Summary |
| Close | **Restore the switch to the baseline**, confirm SPAN removed, normal operation verified; hash and log evidence; reflection; sign-off | **Yes** (rollback) | Evidence Log, sign-off |

**Reflection questions:** (1) What was the anomaly, and which single filter or statistic
exposed it fastest? (2) Which one control gives the biggest security gain for the least
operational risk? (3) What can a SPAN port miss entirely, and how would you cover that gap?

**Things the workbook assumes exist:**

- An **OT Protocol Reference Guide** (OSI layer, Purdue level, ports, security features per
  protocol). **It is not in the repo** (S2-G5).
- Kit Parameter Sheet values `<SPAN_SRC_PORTS>` and `<SPAN_DST_PORT>`, marked "Session 2",
  and `<TR_PCAP_NAME>`, marked "distributed each session".
- The workbook's filter examples cover Modbus, S7comm, DNP3, IEC 104 and CIP. Only S7comm is
  native to the kit hardware (S2-G4).

## 2. How Session 2 differs from Session 1

- **Session 1 is observe-only. Session 2 makes a real config change** on 8 kit switches, then
  rolls it back. Backup, approval and rollback become real logistics for one trainer.
- **Session 1 uses a prepared rack PCAP. Session 2 wants a live capture** from each kit, plus a
  trainer-controlled anomaly.
- It needs **physical cabling** (a capture NIC on the monitor port) at every kit.

## 3. Gaps and risks

- **S2-G12 — ~~EWS-port-as-monitor conflict~~. RESOLVED (S2-D7):** dedicated mirror port + USB
  capture NIC; EWS port stays normal. See §0.
- **S2-G13 — ~~Process reset after the write anomaly~~. CLOSED (S2-D9):** hardware reset buttons
  return the logic to its start state; reset is a button press between pairs/cohorts.
- **S2-G1 — What the SPAN shows** (mostly answered: everything is on the XC208G, S2-D5/D7).
  Still to confirm which physical port the CPU 410 uses (the mirror source) and whether the
  ET 200SP is on the same switch (PROFINET visible) (S2-Q1).
- **S2-G3 — Capture NIC.** Host is Windows + VirtualBox (S2-D4). In VirtualBox, set the capture
  adapter's promiscuous mode to **Allow All** or mirrored frames are dropped. Capture can run on
  the host NIC directly or in a VM with that setting. The USB-to-Ethernet adapter is the likely
  dedicated capture NIC if outcome 2 of S2-G12 applies.
- **S2-G4 — Choice of protocol.** Kit-native: **S7comm** (plus PROFINET RT/DCP if visible).
  Modbus, IEC 61850 MMS/GOOSE and OPC UA exist only in the rack PCAP from Session 1. The
  workbook's anomaly filters are Modbus-flavoured (`modbus.func_code >= 5`).
- **S2-G5 — No OT Protocol Reference Guide exists.** It is needed for Part D validation and
  will be reused in later sessions.
- **S2-G6 — Producing the anomaly.** The S1 PCAP build is blocked because Claude can't generate
  controller-protocol traffic (main tracker Q28). A synthetic S2 anomaly would hit the same
  block. A live anomaly on 8 kits needs one trainer at 8 places at once (S2-Q5).
- **S2-G7 — One trainer, 8 switch changes.** The workbook says each change needs trainer
  approval, a rollback baseline, and a supervised restore. Done one pair at a time, that is
  2–3 min × 8 = ~20 min of trainer time, twice (S2-P3).
- **S2-G8 — Switch access for students.** Pairs need XC208G WBM/CLI credentials with write
  rights. Decide which account, whether it is the same on all kits, and whether it changes
  after the course (S2-Q7).
- **S2-G9 — Restore before the next cohort.** Reset can't use checkpoints (standing
  constraint). The XC208G config must be verified clean after every class, and someone has to
  own that check.
- **S2-G10 — 120 min is tight.** Part D has three tables (W2.5, W2.6, W2.7) plus an AI step.
  W2.6 and W2.7 could take most of an hour on their own.
- **S2-G11 — Claude's boundary with the kits.** CLAUDE.md rule 13 lists L1 devices and cell
  firewalls as out of scope; each kit holds a CPU 410 and an SC646. Working assumption until
  the operator says otherwise: **Claude prepares materials only and never touches a kit**. Any
  kit capture or config is done by the trainer or operator (S2-Q8).
- **Shared with S1** (main tracker): file distribution and evidence collection for 8 kits (Q10),
  AI device and text transfer (Q16), Wireshark version on the kits (Q27), whether the kits are
  physically ready (Q6).

## 4. Proposals (not decided)

- **S2-P1 — Run-sheet draft (1 trainer, 8 pairs).** Assumes S2-P2 (hybrid anomaly) and S2-P3
  (standard change).

  | Time | Trainer | Pairs |
  |---|---|---|
  | 0:00–0:10 | Briefing: scenario, safety rules, **protocol in scope**, the standard change card (S2-P3) | Pre-flight; read the change card |
  | 0:10–0:25 | Projector demo on the XC208G: export config → set up mirroring → packets appear on a capture host → remove mirroring. Brief "what SPAN can miss" | Watch; fill in W2.1 fields as they go |
  | 0:25–0:45 | Rolling approvals: checks each pair's exported baseline file, initials the card | Export baseline → approval → apply SPAN → cable USB NIC → verify foreign traffic → **start the 15–20 min capture** |
  | 0:45–1:05 | Floats | Capture runs in the background. Meanwhile Part B (Protocol Hierarchy) on the **trainer PCAP**; stop and save their own capture at ~1:05 |
  | 1:05–1:35 | At ~1:10 hint "something unusual happens in the trainer capture" | Part C on the trainer PCAP: filters, W2.3, W2.4, find the anomaly. W2.2 from both captures |
  | 1:35–1:50 | Floats | Part D: W2.5 + AI prompt, W2.6, W2.7 |
  | 1:50–2:00 | Rolling restore checks, then debrief: reveal the anomaly, the fastest filter, what SPAN misses | **Restore switch** → verify → hash evidence → reflection |
  | After class | Verifies all 8 kit switches clean (S2-G9); sign-off from evidence bundles | — |

- **S2-P2 — ~~Anomaly: hybrid golden capture~~. WITHDRAWN (2026-10-14).** Superseded by S2-D2:
  the anomaly is injected live from the Kali VM, not pre-recorded. The anomaly *content* ideas
  below still inform the injector scope (S2-Q12): an unexpected **write** from the control
  network mid-polling; a **diagnostic** read of the CPU; or a **new node** appearing. Final
  choice to be scoped deliberately, not dropped in as attack code.
- **S2-P3 — "Standard change" instead of 8 one-off approvals.**
  - In the briefing the trainer pre-approves **one standard change**: fixed source ports,
    fixed monitor port, direction *both*, a fixed rollback procedure.
  - Each pair fills a one-page **change card** and shows the trainer the exported baseline
    file before applying. The trainer initials it: about 1 min per pair.
  - This still meets the workbook rule (backup + rollback + approval), and it is a real-world
    lesson in itself (standard vs normal change in OT change management).
- **S2-P4 — Protocol in scope = S7comm** for the first cohorts. It is native to the kits, has
  read/write/diagnostic/setup message types (covers the W2.3 spread), and Wireshark dissects it
  well. Protocol B for the W2.5 comparison: **PROFINET RT** if the kit SPAN sees it (contrast:
  layer 2, no IP), otherwise **Modbus/TCP** from the S1 rack PCAP. Later cohorts can switch the
  focus protocol, e.g. Modbus or IEC 61850, using the S1 PCAP.
- **S2-P5 — Claude drafts the OT Protocol Reference Guide**, scoped to the protocols in this
  lab: S7comm, PROFINET RT/DCP, IEC 61850 MMS/GOOSE, Modbus/TCP, OPC UA, SNMP, NTP, syslog.
  One page per protocol: OSI layer, Purdue level, ports, addressing model, function types with
  Wireshark filters, security features and known weaknesses, compensating controls. It doubles
  as the source for the W2.5/W2.7 answer key.
- **S2-P6 — Standard SPAN port plan, the same on every kit.** Fixed values for
  `<SPAN_SRC_PORTS>` and `<SPAN_DST_PORT>`, labelled on the kit switch, pre-filled on the Kit
  Parameter Sheet. Depends on S2-Q1.

## 5. Open questions

| # | Question | Status |
|---|---|---|
| S2-Q3a | Exact XC208G **mirror config + removal steps** (WBM or CLI). Needs the kit **firmware version**; feasibility is near-certain (S2-D7) | OPEN (needs firmware) |
| S2-Q1 | Which XC208G port is the **CPU 410** on (the mirror source)? Is the **ET 200SP** on the same switch (PROFINET visible)? Which port is spare for the USB capture NIC? All 8 kits identical? | OPEN |
| S2-Q2 | What exactly makes up the live traffic (OS/engineering polling, OPC, LLDP/DCP)? Needed to set W2.2 expectations | OPEN |
| S2-Q3 | ~~Hypervisor / capture NIC~~ | **ANSWERED (S2-D4):** Windows + VirtualBox; promiscuous = Allow All |
| S2-Q4 | **Trainer demo:** on the rack XC208G, or on a spare/trainer kit at the projector? Is there a 9th (trainer) kit? | OPEN |
| S2-Q5 | ~~Anomaly source~~ | **DECIDED (S2-D2):** live Kali S7comm injection; no synthetic PCAP |
| S2-Q6 | ~~Protocol in scope~~ | **DECIDED (S2-D8):** S7comm only |
| S2-Q7 | Which XC208G account do pairs use (write rights)? Same on all kits? Password changed after the course? | OPEN |
| S2-Q8 | ~~Does Claude touch kits?~~ | **DECIDED (S2-D6):** yes, when reachable; record a CLAUDE.md scope note first |
| S2-Q9 | Approval model: standard change (S2-P3), or individual approval per pair as the workbook literally says? | OPEN |
| S2-Q10 | Does an OT Protocol Reference Guide already exist outside this repo? If not, should Claude draft it (S2-P5)? | OPEN |
| S2-Q11 | Is Part D allowed to finish as homework (W2.6/W2.7) if time runs out? | OPEN |
| S2-Q12 | **Injector scope:** which S7 function, read vs write, payload, and what it leaves behind? How is it triggered (on launch / timer / loop / trainer)? | OPEN |
| S2-Q13 | ~~Process reset~~ | **ANSWERED (S2-D9):** hardware reset buttons; button press between pairs |
| S2-Q14 | **Injector deployment:** how is the tool placed identically on all 8 Kali VMs, and timed to land inside each capture window with one trainer? | OPEN |

## 6. Prep task list

Tasks are added as decisions land.

| # | Task | Owner | Status |
|---|---|---|---|
| S2-T1 | Answer kit-reality questions S2-Q1 to S2-Q3 (inspect one kit) | Operator | TODO |
| S2-T2 | Verify XC208G details for the kit firmware: mirroring options, whether the monitor port still forwards normal traffic, config export/restore path | Claude (from the manual) + operator check | TODO |
| S2-T3 | Trainer run-sheet + trainer script for the demo | Claude | TODO (after S2-P1 agreed) |
| S2-T4 | Student SPAN change card (1 page) + restore checklist | Claude | TODO |
| S2-T5 | OT Protocol Reference Guide | Claude | TODO (S2-Q10) |
| S2-T6 | Record the golden capture with the anomaly on a kit | Operator/trainer | TODO (S2-Q5) |
| S2-T7 | Answer key: W2.2–W2.7 + reflection, from the golden capture and the guide | Claude | TODO |
| S2-T8 | Post-class kit switch verification checklist (S2-G9) | Claude | TODO |
| S2-T9 | Dry run on one kit: full Part A → restore, timed | Operator | TODO |

---

## Decision Log

| ID | Date | Decision | Rationale |
|---|---|---|---|
| S2-D1 | 2026-10-14 | Kit wiring is fixed: two external cables (WAN, EWS); no re-cabling | Operator |
| S2-D2 | 2026-10-14 | Anomaly is injected **live** from the Kali VM (rogue S7comm at the CPU 410); **no synthetic PCAP** for S2 | Operator; live traffic exists, more realistic, feeds Session 3 |
| S2-D3 | 2026-10-14 | SPAN is done by reconfiguring the **EWS switch port as the monitor port**; capture on the host; restore after | Operator |
| S2-D4 | 2026-10-14 | Kit host = **Windows + VirtualBox**; EWS and Kali VMs run on it | Operator |
| S2-D5 | 2026-10-14 | **Live OT traffic exists** on the kit | Operator |
| S2-D6 | 2026-10-14 | Claude **may** work directly on kit devices; they are currently arranged unreachable by design. Record a CLAUDE.md scope note before first touch | Operator |
| S2-D7 | 2026-10-14 | SPAN = **dedicated mirror port + USB capture NIC**. EWS cable bridged to both EWS and Kali VMs; EWS port stays normal; USB adapter on an additional XC208G port set as mirror destination | Operator; removes dependence on dual-function monitor-port behaviour |
| S2-D8 | 2026-10-14 | **Focus protocol = S7comm only** | Operator; native to the kit, and the injector is S7comm |
| S2-D9 | 2026-10-14 | Injection is an S7comm **write that drives physical outputs (lights)**; kit has **hardware reset buttons**; reset between pairs is a button press | Operator |

## Changelog

- 2026-10-14: Tracker created. Read M1 Session 2 and mapped it to the lab; listed gaps
  S2-G1 to S2-G11, proposals S2-P1 to S2-P6, questions S2-Q1 to S2-Q11 and tasks S2-T1 to S2-T9.
- 2026-10-14: Operator described the kit reality. Logged S2-D1 to S2-D6; added §0 (kit reality)
  and the critical SPAN-port risk S2-G12 + S2-G13; withdrew S2-P2 (golden capture) in favour of
  live Kali injection; answered S2-Q3/Q5/Q8, added S2-Q3a, S2-Q12 to S2-Q14.
- 2026-10-14: Operator resolved the SPAN design (S2-D7: dedicated mirror port + USB NIC, EWS
  port stays normal) and fixed the focus protocol (S2-D8: S7comm) and the injection/reset
  (S2-D9: write-to-lights with hardware reset buttons). Closed S2-G12/G13; answered
  S2-Q1(partly)/Q6/Q13. Critical path is now just the exact XC208G mirror steps (S2-Q3a).
