# OT Cyber Drill — Preparation Tracker

Workbook: `Lab-Modules/OT_Cyber_Drill_Workbook.docx` ("OT Cyber Drill Facilitator Workbook —
Red Team | Blue Team | White Team"; scenario: enterprise-to-OT compromise and cyber-physical
process manipulation; fictional pharmaceutical CSTR batch PB-2027-091).

ID prefix for this activity: **`DR-`** (DR-D1, DR-Q1, DR-G1, ...). Main-tracker decisions D2
(class shape), D5 (AI policy) and D12 (reality beats the drawing) are assumed to apply until the
operator says otherwise (DR-Q1).

**Status tags:** `OPEN` · `PROPOSED` · `DECIDED` · `TODO` · `IN PROGRESS` · `DONE`

---

## 1. Status at a glance

| Phase | Status | Next step |
|---|---|---|
| Read workbook + lab facts | DONE (2026-10-19) | — |
| Design: drill shape, teams, "both sides learn" | PROPOSED (§7) | Operator answers DR-Q1–DR-Q6 (shape) |
| Range design: targets, Red source, telemetry, guardrails | OPEN (§6, §8) | Operator answers DR-Q7–DR-Q12 (range) |
| Prep task list | Not started | After shape + range decisions |
| Inject artefacts (SIM packets, training historian data) | Not started | After DR-Q4 / DR-Q10 |
| Classroom / control plan, team briefs, answer book | Not started | After decisions |
| Dry run | — | — |

## 2. Sources

- Workbook: `Lab-Modules/OT_Cyber_Drill_Workbook.docx` (13 sections; facilitator copy; only
  image is the NP logo, so **no topology is attached**: the G0 checklist asks for one).
- Lab facts: `config/inventory.yaml` (DMZ/L3/L4/L5 observed), `CLAUDE.md` status log.
- FW-South running config as of 2026-10-19 (`Backups/20261019-dmz-ot-rule/`), FW-North config
  (`Backups/20261019-fw-logging/`): read from the saved backups only, no device contacted.
- Telemetry: `tools/splunk-uf/README.md` (UF hosts, LAB / ESCU / LAB NET alerts),
  `tools/sysmon/README.md`, `docs/SPLUNK_SCRIBBLER_PLAN.md`.
- Template: `Lab-Modules/M1-S1/` (tracker, classroom plan, answer book);
  `Lab-Modules/M2-S2/STAGING_LOG.md` (closest analogue: planted activity + detection matrix).
- Memories: lab-activities-planning, no-vm-checkpoints-licensing, syslog-onboarding,
  splunk-scribbler-plan, splunk-uf-rollout, ssm-sensor-activation, l1-addresses-observed.

## 3. Standing constraints

- **CLAUDE.md rule 13.** Claude and the Lab Console never touch L2 and below (rack ES01, OSS01,
  OSC, CPU 410/410F, IO racks, L1/L2 switches, OT firewall). Anything the drill needs there is
  done by the trainer by hand, or is a SIM artefact built offline on MC01.
- **Rule 14.** Any range preparation that changes a lab system (drill account, logging, firewall
  guardrail, files placed on a host) is an operator-approved change with backup and rollback.
- **No Hyper-V checkpoints of lab VMs** (licensing). Drill recovery (G14) has to use scripted,
  app-level baselines, not snapshots.
- **SIS is never contacted** (workbook freeze condition and course rule). No 192.168.2.* traffic
  in any synthetic artefact.
- **Class shape (D2, assumed):** ~16 students, **1 trainer**, 8 kits. Nothing may need a second
  staff member (see DR-G7: the workbook assumes seven roles).
- **Workbook rules themselves:** LIVE / SIM / BLOCK / FREEZE labels; a blocked path never becomes
  an assumed compromise; White approves every state-changing action; no broad scans, DoS,
  credential harvesting, persistence or production writes.

## 4. What the workbook asks for

| § | Part | Content | Who uses it |
|---|---|---|---|
| 1 | Exercise overview | Profile, 6 objectives (detect, scope, protect process, contain, recover, communicate), scope / out of scope | White |
| 2 | Roles + ground rules | Director, White, Red, Blue, OT Ops/Gold, Safety Officer, Observers; 8 freeze conditions; G0 readiness checklist (8 items) + signatures | All |
| 3 | Environment | 12 assets mapped to zones and drill use; telemetry table (8 sources) | White, Blue |
| 4 | Scenario | Narrative; Branches A (Red progresses), B (Blue blocks early), C (telemetry unavailable); end state; Red objectives RT-01–RT-05 | White, Red |
| 5 | Blue workflow | 9 phases Detect → Communicate; Blue incident log | Blue |
| 6 | Inject workbook | INJ-01–INJ-12 (T+10 → T+200), control cards with evidence IDs, gate matrix G0–G14 | White only |
| 7 | Master timeline | T+00 → T+250; target criteria (detect ≤10 min, identify ≤20, contain ≤15, process ≤10); time metrics | White |
| 8 | Attack/detection matrix | 12 moves mapped to ATT&CK for ICS (T0822 … T0832); adjudication table | White, AAR |
| 9 | Scoring | Anchors + critical-failure rule; Blue 100 pts (8 categories), Red 100 pts (7 categories) | White |
| 10–13 | Observation log, Blue decision log + 6 key questions, AAR, remediation tracker, closure | All |

**Move types (by workbook label):**
- **LIVE-capable:** 01 remote session, 02 benign command, 03 repeat sign-in, 05 inert file,
  06 named discovery, 07 engineering-path attempt, 08 read-only process view, 09 single benign
  connection, 11 one bounded simulator change.
- **SIM by design:** 04 privilege-escalation evidence, 10 missing-alarm sequence,
  12 historian/operator-record conflict.

**Key observation:** the workbook is **facilitator-only**. Red and Blue have no student-facing
material yet (briefs, action cards, evidence packs, log sheets). Those have to be produced.

## 5. Terms-to-lab mapping (DRAFT: reality vs the workbook's zone labels)

| Workbook asset (zone as written) | Real lab asset | Real zone | Drill use proposed | Note |
|---|---|---|---|---|
| Remote Access Client (L5) | L4H1_RAC 10.5.20.10 