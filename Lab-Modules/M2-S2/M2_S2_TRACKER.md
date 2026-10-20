# M2 Session 2 — Rogue Asset Detection, Baseline Deviation and Exposure Review · Preparation Tracker

Tracks how workbook **Module 2, Session 2** will be run in this lab: discussion, decisions,
open questions and preparation progress. Everything for this activity lives in
`Lab-Modules/M2-S2/`.

IDs are prefixed `M2S2-` so they never clash with M1-S1 (`D1`–`D23`), M1-S2 (`S2-`) or M2-S1
(`M2S1-`). All-session decisions from M1-S1 apply: **D2** (16 students, 1 trainer, 8 kits),
**D5** (web AI chat on BYOD, lab IPs may be pasted), **D12** (the lab as it really is wins over
the drawing), **D20** (no SIS traffic in any synthetic capture).

**Status tags:** `OPEN` · `PROPOSED` · `DECIDED` · `TODO` / `IN PROGRESS` / `DONE`

---

## 1. Status at a glance

| Phase | Status | Next step |
|---|---|---|
| Workbook read and mapped to the lab | DONE (2026-10-14) | — |
| Tracker draft (§1–§8) | DONE (2026-10-14) | — |
| **Activity design review** (tables, progression, how it teaches) | PROPOSED: `ACTIVITY_DESIGN_REVIEW.md` | Operator answers M2S2-Q1, Q2 |
| **Planted deviations** (what, how staged, how caught) | PROPOSED: `STAGING_LOG.md`; K3 and SSM settled (M2S2-D1, D2) | Operator answers M2S2-Q2 to Q6 |
| Standard scan port list | DECIDED (M2S2-D3): 3389 added, S1 and S2 identical | Confirm the reading of the operator's answer (Q9) |
| Staging / reset / check scripts | DRAFT: `staging/` (untested; kit facts are placeholders) | Kit facts (Q4), then a dry run on one kit |
| Kit facts (IPs, segments, CPU rack/slot, scan host) | DEFERRED (same as M2S1-Q4/Q5) | Needed before the dry run |
| Rack S2 capture (synthetic) | TODO, depends on the M2-S1 spec (M2S1-D2, not built) | After M2-S1's capture is built |
| Classroom plan | TODO | After the design review is agreed |
| Answer book | TODO | After the dry run (numbers must be observed) |
| Student materials | TODO | After the classroom plan |
| Dry run | — | — |

## 2. Sources

- **Workbook:** `Lab-Modules/Module_2_Workbook__OT_Asset_and_Configuration_Management.docx`,
  Session 2 (tables W2.1–W2.7, evidence naming `M2-W2-…`, 3 reflection questions).
- **M2-S1 (the baseline this session diffs against):** `Lab-Modules/M2-S1/M2_S1_TRACKER.md`
  (G6 scan mismatch, G13 one spec for both captures, P4 standard scan, P5 collection script) and
  `ACTIVITY_DESIGN_REVIEW.md` (three-bucket reconciliation, confidence rubric).
- **M1-S2 kit reality:** `Lab-Modules/M1-S2/M1_S2_TRACKER.md` §0: kit host = Windows +
  VirtualBox with the EWS VM and the Kali VM bridged on the EWS cable (S2-D4, S2-D7); XC208G
  mirror port + USB capture NIC (S2-D7); live OT traffic (S2-D5); Kali S7 injector (S2-D2).
- **Observed inventory:** `config/inventory.yaml`: SINEC NMS on MaintServer 192.168.30.11, SSM
  10.1.20.18 (web 8443), SSM sensor 10.1.20.19.
- **NMS reality:** `docs/NMS_ONBOARDING.md`: NMS monitors only the onboarded network devices
  (SNMPv3); discovery restriction `L1L2_noPROFINET` covers 192.168.1.0–192.168.4.255 and
  192.168.20.0/24; SSM sits on SW-DMZ Gi0/4.
- **Memories:** lab-activities-planning, no-vm-checkpoints-licensing,
  phase-reports-and-visible-browser, nms-onboarding-project.

## 3. Standing constraints

- **CLAUDE.md rule 13.** Claude and the Lab Console never touch rack L2 or below. Every kit and
  rack staging action in `STAGING_LOG.md` is done **by the trainer by hand**. Claude only writes
  the scripts and the synthetic capture spec. The kits are unreachable from MC01 (S2-D6).
- **Rule 14, observe-only.** Claude may check (read-only) that NMS/SSM picked up R1 on the DMZ,
  only with the operator's go-ahead.
- **No Hyper-V checkpoints of lab VMs.** Kit reset is by script plus a verified empty diff, not
  by snapshots.
- **Class shape (D2):** 1 trainer, 8 pairs, 120 min. Nothing may need a second staff member.
- **SIS silent (D20):** no 192.168.2.* traffic in the S2 synthetic capture; never a scan target.
- **Workbook safety rules:** OT-safe scanning only, approved targets, conservative timing.
  Planted rogue traffic is **read-only** (no S7 writes) and rate-limited.
- **Method identity with S1.** The diff is only honest if S2 uses exactly the S1 scan, capture
  point and collection script (M2S1-G6, G13).

## 4. What the workbook asks for

**Duration:** 120 min. **Unit:** a pair per kit. **Scenario:** a rogue/unauthorised system,
service or configuration change appears after the S1 baseline. Detect, investigate, classify,
report.

| Part | What happens | Tool | Output |
|---|---|---|---|
| Pre-flight | S1 artefacts available and unmodified; same `<APPROVED_TARGETS>`; NMS/SSM access; trainer confirms the "deviation window" is active | — | Ticked checklist |
| A — Import baseline | Work on copies; check hashes against the S1 log | PowerShell | **W2.1** Baseline Import Checklist |
| B — Re-discover | Trainer introduces rogue system(s) on the rack (and possibly the kit). Repeat S1 discovery: capture, `nmap -sn -PR`, `-sT` port scan, PowerShell; `ndiff` | Wireshark, Nmap, PowerShell | **W2.2** Re-Discovery Results |
| C — Compare | Classify every difference New / Missing / Modified / Undocumented | — | **W2.3** Baseline vs Current Diff |
| D — Investigate | Each deviation through Wireshark, Nmap/host, SINEC NMS/SSM; AI correlates and rates significance | all + AI | **W2.4** Investigation Log, **W2.5** SINEC Dashboard Observations |
| E — Classify, report | Rogue / Legitimate but Undocumented / Temporary Maintenance / Unresolved; disposition, owner, due; one-page report | — | **W2.6** Classification & Disposition, **W2.7** Summary Report |
| Close | Evidence `M2-W2-<KIT_ID>-…`, SHA-256, reflection, sign-off | PowerShell | Evidence Log |

**Reflection:** (1) which source first revealed the rogue, and would it have been caught
without SINEC; (2) was a real deviation hidden by a benign one; (3) what monitoring change would
shorten time-to-detection.

## 5. Terms-to-lab mapping

| Workbook says | In this lab |
|---|---|
| "Rogue systems on the Trainer Rack" | **R1**: a real device on a spare SW-DMZ port (DMZ, in scope), seen live by NMS/SSM and also present in the synthetic S2 rack capture. **R2**: synthetic only |
| "(and possibly your kit)" | **K1–K4**, staged by the trainer on every kit (`STAGING_LOG.md`) |
| "Same monitor point" | The same kit capture point as S1 (M2S1-Q11 still open) + the S2 rack capture built from the S1 spec |
| `nmap -sn -PR` / port scan | The **standard scan** from S1 (M2S1-P4), port list + 3389 (M2S2-D3). Not the workbook's S2 command, which differs from S1 |
| `<SINEC_NMS_URL>` | https://192.168.30.11 |
| `<SINEC_SSM_URL>` | https://10.1.20.18:8443 (sensor 10.1.20.19 not yet configured; M2S2-D2) |
| "Deviation scenario window is active" | The trainer's T-30 staging check passed (STAGING_LOG §4) |
| "Owner" in W2.6 | A role from a fixed list on the definitions card (OT engineer, site IT, vendor, security) |

## 6. Observations and gaps

- **M2S2-G1 — Five of seven tables have the same row key ("the deviation").** W2.3, W2.4, W2.5,
  W2.6 and W2.7 hold the same 4–6 items, each rewritten. W2.2 re-copies the scan output. Most of
  the time goes on copying; classification comes last and gets rushed.
- **M2S2-G2 — S1 and S2 discovery methods differ in the workbook** (`--disable-arp-ping` vs `-PR`;
  S2 drops 34962-34964). That creates false New/Modified rows before anything is planted
  (inherits M2S1-G6).
- **M2S2-G3 — SINEC can't see the kits.** NMS only watches onboarded network devices; the kits are
  not among them. The SSM sensor isn't configured today. W2.5 only has true content for a
  deviation placed where NMS/SSM look (hence R1 on the DMZ; M2S2-D2).
- **M2S2-G4 — "Undocumented" is used on two axes.** It's a change type in W2.3 and part of a
  classification in W2.6 ("Legitimate but Undocumented"). Students will mix them up.
- **M2S2-G5 — No change record exists in the workbook.** Without one, "Temporary Maintenance" vs
  "Rogue" is a guess, not an evidence check.
- **M2S2-G6 — Scan host conflict.** If Kali is the S1 scan host, Kali is in the S1 baseline and
  can't appear as "New" (K1) in S2. The scan host must be something else in **both** sessions.
- **M2S2-G7 — K4 needs Kali on the ET 200SP's L2 segment.** The drawing puts the ET 200SP on
  VLAN A (control) and the EWS (whose cable Kali shares) on VLAN B. If they differ, Kali can't
  claim the ET 200SP's IP on-link. Kit topology is unconfirmed (M2S1-Q4).
- **M2S2-G8 — The S2 rack capture depends on the M2-S1 spec, which isn't built** (M2S1-D2). It
  must also carry R1's **real** MAC/IP so the wire and SINEC agree.
- **M2S2-G9 — Re-running S1 by hand costs ~30 min.** Repetition of the *method* is required;
  repetition of the *typing* isn't. Use the S1 scan card and collection script.
- **M2S2-G10 — NMS discovery is periodic.** NMS "first seen" is when discovery ran, not when R1
  was plugged in. The discovery schedule on the DMZ range is unknown (Q6).
- **M2S2-G11 — K3 side effects (accepted, M2S2-D1).** With the ET 200SP gone the CPU 410 may go to
  STOP; the HMI will alarm. That's an extra clue students may notice. S7 reads (K1) still work in
  STOP. Reset needs a CPU restart and a check that the ET 200SP is back in data exchange.
- **M2S2-G12 — K3/K4 ordering hazard.** The CPU assigns the ET 200SP its IP over DCP at startup.
  If Kali still holds that IP when the ET 200SP is reconnected, the device can fail its
  duplicate-address check and stay down. Kali's alias must be removed **first**.
- **M2S2-G13 — Evidence Log is typed by hand.** A `Get-FileHash | Export-Csv` line does it.

## 7. Proposals (not decided)

- **M2S2-P1 — Seven tables to three plus a checklist** (design review §3). Pre-flight box (W2.1),
  **T1 Baseline vs Now** (W2.2 + W2.3), **T2 Deviation Case Sheet** (W2.4 + W2.5 + W2.6), **T3
  Handover** (W2.7). Maps 1:1 to the workbook deliverables, as M1-S2 did.
- **M2S2-P2 — Planted set** (`STAGING_LOG.md`): K1 rogue Kali (New → Rogue); K2 RDP on EWS
  (Modified → Legitimate but undocumented); K3 ET 200SP off for a ticketed swap (Missing →
  Maintenance); K4 Kali takes the ET 200SP's IP during K3 (Modified → Rogue hidden by benign);
  R1 rogue on the DMZ (New → Rogue, SINEC confirms); R2 one-frame unknown in the rack capture
  (New → Unresolved).
- **M2S2-P3 — Change calendar handout** (draft in STAGING_LOG §6). Issued at checkpoint 1, *after*
  pairs have their diff, so detection is unbiased and classification is an evidence check.
- **M2S2-P4 — Definitions card:** change type = *what* differs (New / Missing / Modified /
  Undocumented); classification = *why* (Rogue / Legitimate but undocumented / Maintenance /
  Unresolved). "Undocumented" = S1's "seen, not documented" bucket, still unresolved.
- **M2S2-P5 — Interaction shape:** 2 checkpoints + 1 SINEC demo + debrief reveal (design review §5).
- **M2S2-P6 — Scripted staging and reset; the reset proves itself** with the students' own tool:
  re-run the standard scan, `ndiff` against the S1 baseline, empty diff = clean kit.
- **M2S2-P7 — Scan host = the kit host OS** (Windows, already runs Wireshark for the M1-S2 USB
  capture NIC), in both S1 and S2. Keeps Kali out of the S1 baseline (G6) and keeps Nmap/Npcap
  off the PCS 7 EWS. Needs the kit host to have an address on the kit network (Q3).
- **M2S2-P8 — Where the AI is expected to slip:** calling every New device malicious, or explaining
  K4 away as "the ET 200SP was replaced during maintenance" (plausible, but the MAC OUI is
  VirtualBox, not Siemens); inventing SINEC alert names. To confirm in the dry run.

## 8. Open questions

| # | Question | Status |
|---|---|---|
| M2S2-Q1 | Adopt the three-table structure (P1)? | OPEN |
| M2S2-Q2 | Adopt the planted set K1–K4, R1, R2 (P2)? | OPEN (K3 implicitly kept by D1) |
| M2S2-Q3 | Scan host for **both** S1 and S2: the kit host (P7), the EWS VM, or something else, but **not** Kali. Does the kit host have an IP on the kit network? (links M2S1-Q5) | OPEN |
| M2S2-Q4 | Kit facts for the scripts: PLC / ET 200SP / EWS IPs; is Kali's bridged NIC on the ET 200SP's L2 segment (G7)? CPU 410 rack/slot for S7; Kali interface name; a free IP for Kali per kit | DEFERRED (with M2S1-Q4) |
| M2S2-Q5 | R1: which device (laptop or Pi), which spare SW-DMZ port, which free DMZ IP? | OPEN |
| M2S2-Q6 | NMS discovery schedule on the DMZ range: how often does it run? Stage R1 the day before so NMS finds it on its own? | OPEN |
| M2S2-Q7 | SINEC access for students: projector demo only, or a read-only account per pair? | OPEN (default: projector + screenshots in the case sheet) |
| M2S2-Q8 | Staging time: kit plants at T-30 min; R1 the day before (so NMS/SSM have a first-seen time)? | OPEN (default as written) |
| M2S2-Q9 | Confirm the reading of "We will let it discover" as *3389 goes into the standard port list so Nmap finds K2* (M2S2-D3), and R1 is left to NMS's own discovery (no manual add) | OPEN (confirm) |
| M2S2-Q10 | Change calendar format: paper handout or a screenshot of a ticket system? | OPEN (default: paper) |

## 9. Prep task list

| # | Task | Owner | Status |
|---|---|---|---|
| M2S2-T1 | Draft staging / reset / check scripts (`staging/`) | Claude | DONE (draft, untested) |
| M2S2-T2 | Add 3389 to M2-S1's standard port list (cross-session, D3) | Claude | DONE (M2S1-P4 note) |
| M2S2-T3 | Supply kit facts (Q4) and the scan host (Q3) | Operator | TODO |
| M2S2-T4 | Fill script parameters; dry run on one kit: stage, run the full student procedure, record real outputs, reset, prove an empty diff | Trainer + operator | TODO |
| M2S2-T5 | S2 rack capture spec `tools/lab-pcap/spec/m2s2.yaml` = M2-S1 spec + R1 (real MAC) + R2 | Claude | TODO (after M2-S1 spec) |
| M2S2-T6 | Student worksheet (T1–T3), definitions card, change calendar | Claude | TODO (after Q1/Q2) |
| M2S2-T7 | Classroom plan | Claude | TODO |
| M2S2-T8 | Answer book from the dry-run outputs + tshark on the S2 capture | Claude | TODO |
| M2S2-T9 | Configure the SSM sensor to capture DMZ traffic (assumed by D2) | Operator | **BLOCKED on a decision:** sensor 10.1.20.19 activated 2026-10-16, but its M port (eno3) is on the **SW-SAS (L1, 192.168.3.30) SPAN**, not SW-DMZ, so it will not see R1. Options: give the server's integrated sensor a SW-DMZ SPAN, or change the SSM part of the demo |

## 10. Build status

**Not built.** The S2 rack capture follows M2S1-D2 (assumed, not built). When built: spec
`tools/lab-pcap/spec/m2s2.yaml` derived from `m2s1.yaml`, validation gate (0 malformed, expected
protocol hierarchy, no 192.168.2.*), SHA-256 recorded here and in the answer book. R1's MAC/IP in
the spec must match the real R1 device (G8).

## 11. Decision log

| ID | Date | Scope | Decision | Rationale |
|---|---|---|---|---|
| M2S2-D1 | 2026-10-14 | M2 S2 | **K3 kept:** the ET 200SP is disconnected for the ticketed "module swap". The CPU 410 going to STOP is **acceptable**. Reset includes a CPU restart and a check that the ET 200SP is back in data exchange | Operator: "it's fine even if the process stops". Gives the Missing → Maintenance case and the window that hides K4 |
| M2S2-D2 | 2026-10-14 | M2 S2 | **SSM sensor:** not configured today; **assume it will capture the traffic R1 needs** (DMZ). SSM evidence in the answer book is provisional until a dry run | Operator. Same pattern as M2S1-D2 (assume the lab will be ready) |
| M2S2-D3 | 2026-10-14 | M2 S1 + S2 | **3389 added to the standard scan port list**, identical in S1 and S2, so Nmap discovers K2 (RDP enabled on the EWS). R1 is left to NMS's own discovery, no manual add | Operator: "We will let it discover". Claude's reading; confirm (Q9). K4 still shows a case Nmap misses |

## 12. Changelog

- 2026-10-14: Tracker created. Read Session 2 end to end against M1-S1, M1-S2 and M2-S1. Wrote
  `ACTIVITY_DESIGN_REVIEW.md` (7 → 3 tables, progression, interaction shape) and `STAGING_LOG.md`
  (planted set, detection matrix, staging order, change calendar draft). Gaps G1–G13, proposals
  P1–P8, questions Q1–Q10.
- 2026-10-14: Operator answered: CPU STOP acceptable (D1); SSM assumed to capture (D2); "let it
  discover" (D3, reading to confirm). Draft scripts in `staging/`; M2-S1 P4 updated with 3389.
- 2026-10-16: SSM sensor 10.1.20.19 licence activated (server SSM V4.11.0). Before activation the
  sensor showed `wireguard: Failed` / missing `wg0.conf`; activation delivers that tunnel config.
  Server is on UTC, sensor on +08:00 (clocks agree in UTC). Not yet bound or mirrored (T9).
- 2026-10-16: Operator connected the sensor's M port (eno3) to the **SW-SAS 192.168.3.30 SPAN** (L1
  SAS cell). First sensor capture (100 pkts / 0.48 s) held only MRP test frames (MRA, ring open) from
  74:fc:45:b6:4a:bd and 74:fc:45:b6:4c:1d; too short to show GOOSE/MMS. Passive analysis only (rule 13).
  Advised: keep Active Probing off and no IP on the M port. D2's DMZ assumption no longer holds (T9).
- 2026-10-16: Second sensor capture (5000 pkts / 21.7 s). Mirror port: **0 unicast frames**, only
  flooded broadcast/multicast (MRP from the two L1 switches, ARP from 192.168.1.254, a WAGO
  `00:30:de` ARP probe for 192.168.4.10). **No GOOSE, no MMS, no SIPROTEC/A8000 MACs.** So the
  SW-SAS SPAN is not delivering the cell's traffic (operator to check SW-SAS mirroring). H1 side is
  healthy: LLDP confirms SW-DMZ (XC416-8, FW V01.04.01) port 6, 802.1X EAP Success, WireGuard carrying
  the TLS 5046 log stream to the server.
