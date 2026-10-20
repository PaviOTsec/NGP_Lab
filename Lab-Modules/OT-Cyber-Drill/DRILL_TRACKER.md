# OT Cyber Drill — Preparation Tracker

Single source of truth for preparing the **OT Cyber Drill** (Red / Blue / White team exercise)
from `Lab-Modules/OT_Cyber_Drill_Workbook.docx`. This is **not** an M1/M2 familiarisation
session — it is a facilitated, timed, scored incident-response exercise. Different shape,
different deliverables.

**Status tags:** `OPEN` · `PROPOSED` · `DECIDED` · `TODO` / `IN PROGRESS` / `DONE`
**ID prefixes:** decisions `DD#`, questions `DQ#`, gaps `DG#`, proposals `DP#`, tasks `DT#`
(the `D` = Drill, so they never collide with M1/M2 IDs).

---

## 1. Status at a glance

| Phase | What | Status | Next step |
|---|---|---|---|
| 0. Read & map | Workbook parsed; named assets mapped to real lab | **DONE** | — |
| 1. Design frame | Both-sides learning model; LIVE/SIM split; class shape | **DECIDED** (DD3–DD7) | — |
| 2. Scenario build | Per-inject LIVE/SIM decision; detection key; build list | **DONE (v1)** → `WHITE_TEAM_DESIGN.md` | — |
| 2b. Red×Blue options | Full option tree per stage, Kali→RAC Stage 0, Zeek/Suricata | **DONE (v1)** → `RED_BLUE_OPTIONS.md` | Operator: Stage-4 route, SPAN placement, Stage-0 default |
| 2c. Golden path | The one highlighted Red route, fully mapped + flagged (DD12) | **DONE (v1)** → `GOLDEN_PATH.md` | Operator: GP open #1–4 (seed host, isolated-segment confirm, light, INS web/RADIUS) |
| 2d. Flag registry | GP-1..GP-4 artifacts + scoring key (stage-based, DD10) | TODO | After GP decisions |
| 3. White Team pack | 12 inject artefacts (real or labelled SIM), gate cards, truth log | TODO | Surrogate (DT5) + posture (DT6) + packets (DT7) |
| 4. Blue enablement | Confirm the real detection stack answers each detection opportunity | IN PROGRESS | Detection key drafted (§4 of design); verify each search live later |
| 5. Facilitator run | Minute-by-minute White run-sheet; room/role layout; dry run | TODO | After phase 3 |

---

## 2. Sources

- **Workbook:** `Lab-Modules/OT_Cyber_Drill_Workbook.docx` (Facilitator / White Team copy).
  Scenario: Enterprise-to-OT compromise + cyber-physical process manipulation; fictional
  pharmaceutical CSTR batch **PB-2027-091**. 13 sections, 12 injects (INJ-01…12), 15 gates
  (G0…G14), ATT&CK-for-ICS detection matrix, Blue+Red scoring to 100 each.
- **Inventory (observed):** `config/inventory.yaml` (DMZ/L3/L4/L5 only; L2 & below excluded).
- **Detection stack already built** (this is the drill's biggest asset — see §5):
  - Splunk SIEM `DMZH1_SIEM` 10.1.20.15 — UFs on 8 Windows hosts, Sysmon 15.22, XML events,
    12 LAB + 50 ESCU alerts, Security Essentials. (`tools/splunk-uf/`, `tools/sysmon/`)
  - Scribbler log manager `DMZH1_LogServer` 10.1.20.13 — switch + firewall syslog; bridged
    into Splunk index `netdev` with 12 `LAB NET` alerts. **Firewalls currently log deny only.**
  - SINEC NMS on `DMZH2_MaintServer` 192.168.30.11; SINEC INS 10.1.20.21.
  - SINEC Security Monitor `DMZBM_SSM` 10.1.20.18 + sensor .19 (sensor M-port is on the
    **SW-SAS / L1 SAS cell** SPAN, per [[ssm-sensor-activation]] — not the kit/DMZ).
- **Memories:** `lab-activities-planning`, `no-vm-checkpoints-licensing`,
  `phase-reports-and-visible-browser`, `l1-addresses-observed`, `syslog-onboarding`,
  `splunk-uf-rollout`, `splunk-scribbler-plan`, `ssm-sensor-activation`.
- **Template (structure/depth only):** M1-S1 `Lab-Modules/M1-S1/` and M2-S2 `STAGING_LOG.md`
  (trainer-only ground-truth pattern — reused here as the White Team truth log).

## 3. Standing constraints

- **CLAUDE.md rule 13 (L2 & below out of scope).** Claude and the Lab Console never touch
  L2/L1/L0 live: the real Engineering Station (ES01 192.168.20.11), PCS 7 OS Server
  (OSS01 192.168.20.10), CPU 410 / ET 200SP, SIS, or the pharma CSTR cell. The drill's deep-OT
  stages therefore run as **SIM evidence** or against **surrogates we build offline** — which
  is exactly what the workbook already asks for (reference-only controller, simulator-only CSTR
  change, SIM injects for privilege/alarm). Offline artefact building on MC01 touches no device.
- **Drill-specific device config is allowed (DD2).** Operator (2026-10-19): for the drill we may
  change and save a drill-specific config on in-scope devices (firewalls, DMZ/L3 switches/hosts),
  backup-first. This unblocks the "boundary blocks Red" injects and clean deny-logging. It does
  **not** lift rule 13 for L2/L1.
- **No Hyper-V checkpoints of lab VMs** (voids licences, [[no-vm-checkpoints-licensing]]). Reset
  between runs uses config export/restore and app-level snapshots, not VM checkpoints.
- **Workbook safety spine is mandatory and is itself a teaching objective:** EXERCISE FREEZE
  conditions, LIVE/SIM/BLOCK labelling, no contact with SIS/production, every state-change
  White-approved, a blocked path never becomes an assumed compromise. Keep it intact.
- **Class shape (carried from D2):** ~16 students, 1 trainer. For a drill the trainer is
  **White Team / Exercise Director**; students split into Red and Blue (DQ2).

## 4. What the workbook asks for (summary)

| § | Part | Nature |
|---|---|---|
| 1 | Exercise overview, objectives, scope / out-of-scope | Setup + 6 objectives, 2-col scope |
| 2 | Roles (Director, White, Red, Blue, OT Ops/Gold, Safety, Observers), ground rules, **Freeze conditions**, G0 readiness checklist | Governance |
| 3 | OT environment & architecture (11 named assets + telemetry sources) | Mapping target (→ §5 here) |
| 4 | Scenario narrative, 3 branches (A Red progresses / B Blue blocks early / C telemetry gap), end state, 5 Red objectives RT-01…05 | Story + adjudication logic |
| 5 | Blue workflow: Detect→Triage→Investigate→Scope→Contain→Protect→Eradicate→Recover→Communicate; incident log | Blue scaffold |
| 6 | **White Team inject workbook** — 12 injects (plan time, method, signal, expected Blue response), inject control cards (precondition/evidence/alternate), gate control matrix G0–G14 | **Core build** |
| 7 | Master timeline T+00…T+250; pre-exec target criteria; time metrics | Schedule |
| 8 | Attack/Detection matrix — 12 moves → ICS tactic + ATT&CK technique ID + telemetry + detection opportunity | Red↔Blue bridge |
| 9 | Scoring: Blue /100 (8 categories), Red /100 (7 categories); anchors + critical-failure rules | Assessment |
| 10–13 | Observation log, Blue decision log, AAR, remediation tracker | Capture + debrief |

**Timeline shape:** 12 injects at T+10…T+200 (roughly every 15 min), then G13 containment
(T+220) and G14 recovery (T+250). ~4.5 h end-to-end as written — likely trimmed (DQ1).

## 5. Terms → lab mapping (workbook name → real asset → drill treatment)

| Workbook asset (zone) | Real lab asset | Can we drive it LIVE? | Drill treatment |
|---|---|---|---|
| **Remote Access Client** (Ent L5) | `L4H1_RAC` 10.5.20.10 (SINEMA RC client) | Yes — console + creds verified | **LIVE** origin of the exercise account |
| **North Firewall** (Ent/DMZ) | `FW-North` FortiGate 10.4.20.254 | Yes — config + syslog→Scribbler | **LIVE** allow/deny evidence |
| **Maintenance Server** (DMZ/L3) | `DMZH2_MaintServer` 192.168.30.11 (hosts SINEC NMS) | Yes — UF+Sysmon, creds verified | **LIVE** approved pivot + host evidence |
| **South Firewall** (DMZ/Ops) | `FW-South` PA-440 10.1.20.254 | Yes — config + syslog→Scribbler | **LIVE** path verify; drill posture (DD2) |
| **Engineering Station** (Ops Mgmt L3) | real ES01 is **L2** 192.168.20.11 (rule 13) | **No** (L2) | **Surrogate or SIM** — see DG1 |
| **PCS7 OS Server** (Ops Mgmt L3) | real OSS01 is **L2** 192.168.20.10 (rule 13) | **No** (L2) | Read-only **SIM** process view |
| **Historian** (Terminal L2 in wkbk) | `L3H1_Historian` 192.168.30.10 (bare metal, L3) | Partly — **no password yet** (DG2) | **LIVE read if enabled, else SIM** |
| **Operator + Eng Station** (System L2) | Trainee-Kit endpoint / ES01 | No (L2 / kit) | "only if authorised at G0" → leave out or kit-surrogate |
| **CPU 410 / ET 200SP** (L1/L0) | real pharma cell, CPU 410 192.168.1.15 | **No** (rule 13) | **Reference-only**, never touched |
| **Pharmaceutical CSTR** (process model) | real pharma L0 cell | **No** (rule 13) | **Surrogate simulator we build** (DP2) for the G11 bounded change |
| **CPU 410F / SIS** (Safety) | real SIS 192.168.2.x | **No** — excluded | **Excluded; no contact** (as workbook) |
| **SIEM / Log Server / NMS / SSM** | Splunk .15 / Scribbler .13 / NMS .11 / SSM .18+.19 | Yes | **LIVE Blue telemetry** |

**The headline:** everything from **L5 down to L3/DMZ is real and already instrumented**, so the
IT→OT-boundary half of the kill chain can run LIVE with genuine detection. Everything **L2 and
below is reference/SIM/surrogate** — which the workbook was written to accommodate. The two
halves meet at the South Firewall (INJ-07), the natural LIVE→SIM hand-off point.

## 6. The both-sides learning design (PROPOSED — DP1)

The workbook is already built so **both teams learn regardless of who "wins"** (Branches A/B/C).
The job is to make that real on our infra. Design intent:

- **Red learns** the IT→OT kill chain on a realistically segmented network: external remote
  services (T0822), valid-account reuse (T0859), bounded discovery (T0846), cross-boundary
  lateral movement (T0886), OT read/collection (T0801) — but every state-change is White-gated
  and the deep-OT techniques (privilege esc, alarm suppression, parameter change, view
  manipulation) are **SIM challenges, not live exploits**. Red is scored on discipline and
  evidence, not on "popping" the controller.
- **Blue learns** to run the **real stack they built**: Splunk correlation (host auth/Sysmon),
  firewall deny-logs via Scribbler→`netdev`, SSM/NMS OT visibility, and the **independent
  operator record** as the cross-check — then triage, scope (LIVE/SIM/BLOCK/unknown), contain
  with rollback, make a **process-protection / batch decision**, and verify recovery baselines.
- **White learns** facilitation: gate control, inject timing, adjudication, keeping LIVE and SIM
  cleanly separated so nothing fictional is ever scored as real.
- **The pivotal design choice (DP1):** build it so Branch B is *attractive* — i.e. Blue genuinely
  can block Red early (disable the exercise account, deny at FW-South via the drill posture).
  Then White continues with labelled counterfactual SIM packets. This is what makes it a
  *learning* drill rather than a scripted demo: Blue's actions change the live path, and the
  later teaching objectives still land via SIM.
- **Real-world feel (DD3) governs every build choice.** The default for an inject is LIVE and
  hands-on: Red at a real console running a real tool; Blue finding it in a real product UI.
  Surrogates (DP2) exist so the OT half is still *touchable* (a process that actually moves, an
  engineering station you can actually open), not a slide. We drop to paper-SIM only for the two
  techniques that can't be made safe-and-real — a working privilege-escalation exploit and alarm
  suppression on a safety function — and we label those clearly. The aim: when it's over, a
  student can say "I scanned, I pivoted, I changed a setpoint, I watched the trend move" or "I saw
  the logon, I pulled the firewall deny, I pulled the account, I confirmed the process was safe."

**Pairing each inject to a real detection** (what Blue sees if they're watching) is in §8-work
(DT4); the raw material is the existing Splunk/Scribbler/SSM alerts.

## 7. Observations & gaps

- **DG1 — No L3 Engineering Station exists.** The workbook's "Engineering Station (Level 3)" has
  no real counterpart in scope (the real ES is L2). Options: (a) stand up an **engineering-station
  surrogate** on a spare in-scope VM (`DMZH2_Spare`, or the L3/DMZ) with TIA-Portal-like
  artefacts + a snap7 client, so INJ-06/07 have a real target; (b) keep it entirely SIM (prebuilt
  pivot/allow-deny evidence). Leaning (a) for a real boundary lesson. → DQ4.
- **DG2 — Historian has no credential yet.** `L3H1_Historian` 192.168.30.10 `credential: ""`.
  Needed for a LIVE INJ-08 read-only view and the INJ-12 discrepancy. Either the operator sets a
  password (then LIVE), or INJ-08/12 run as SIM/surrogate. → DQ5.
- **DG3 — Firewalls log deny only; allow is unlogged** ([[syslog-onboarding]]). So INJ-01's
  *allow* won't appear in `netdev` — Blue must catch it in **host auth logs** (Splunk UF on
  MaintServer), and the *deny* at INJ-07 is where firewall telemetry shines. This is a real,
  teachable telemetry-shape lesson, not a bug — call it out in the White pack. (Could enable
  allow-logging for the drill under DD2 if we want both, at the cost of noise.)
- **DG4 — SSM sensor watches the L1 SAS cell, not the kit/DMZ/IT path.** So SSM will *not* see
  INJ-01…09 (they're IT/DMZ). SSM's value here is OT-asset/traffic visibility for the process-
  protection stages — or we re-point/add a sensor for the drill (bigger change). Note honestly in
  the telemetry table so Blue isn't scored for an impossible SSM detection (Branch C logic). → DQ6.
- **DG5 — Class split & concurrency.** 16 students as one Red + one Blue + White is a single
  linear drill. Alternative: run 2 parallel Blue cells, or rotate. Affects whether injects are
  delivered once (one range) or replicated. → DQ2.
- **DG6 — Duration.** 4.5 h as written (T+250 + AAR). A lab session is likely ~2 h (M-series) or a
  half-day. Need the real slot before building the timeline. → DQ1.
- **DG7 — Surrogate CSTR must be real enough to "protect".** For G11's bounded non-safety change
  and G12's historian discrepancy to teach process-protection, Blue needs a process they can
  observe and reason about. A Python CSTR model + snap7/Modbus server + a tiny trend view
  (buildable offline, like the lab-pcap stacks) gives that without the pharma cell. → DP2.
- **DG8 — Red team skill assumption.** The drill assumes Red can execute bounded range actions.
  If participants are beginners (M1 was "first contact"), Red needs scripted playbooks per inject
  (the RT-01…05 objectives become step cards). → DQ3.

## 8. Proposals (not decided)

- **DP1 — Both-sides learning model** as in §6: LIVE IT/DMZ half + SIM/surrogate OT half meeting
  at FW-South; make Branch B genuinely reachable. **PROPOSED.**
- **DP2 — Build a surrogate CSTR + engineering-station** offline (snap7/Modbus process sim + a
  trend/Historian stub) on an in-scope VM, so INJ-06/07/08/11/12 have real targets without
  touching L2/L1. Mirrors the `tools/lab-pcap` "real stack, no lab device" pattern. **PROPOSED.**
- **DP3 — Drill firewall posture (DD2):** a saved `drill` config on FW-South/FW-North that (i)
  makes DMZ→OT *not* allow-all so Blue's containment and INJ-07's deny are real, (ii) keeps a
  clean allow for the authorised exercise path. Backup-first, one named snapshot, documented
  rollback. **PROPOSED.**
- **DP4 — White Team truth log** modelled on M2-S2 `STAGING_LOG.md`: the one ground-truth file
  tying each inject to its LIVE/SIM label, artefact, hash, expected signal, and the detection
  matrix — so the inject pack, timeline and scoring key can't disagree. **PROPOSED.**
- **DP5 — Reuse existing alerts as the detection key.** Map each of the 12 ATT&CK moves to an
  existing Splunk LAB/ESCU or `LAB NET` alert (or name the gap). Blue's "detection opportunity"
  column becomes "which alert should fire / which dashboard panel." **PROPOSED.**

## 9. Open questions (for the operator)

| # | Question | Status |
|---|---|---|
| DQ1 | Time budget? | **DECIDED (DD4):** full ~4.5 h / half-day |
| DQ2 | Class split? | **DECIDED (DD5):** one Red + one Blue, trainer = White |
| DQ3 | Participant level? | **DECIDED (DD6):** capstone |
| DQ4 | Engineering Station surrogate vs SIM? | **DECIDED (DD7):** build surrogate |
| DQ5 | Historian LIVE vs SIM? | **DECIDED (DD11):** LIVE — has a credential; operator sets/confirms pw |
| DQ6 | SSM vs other network visibility? | **DECIDED (DD9):** Zeek + Suricata on the drill-path SPAN |
| DQ7 | Real pharma CSTR model vs build surrogate? | **DECIDED (DD7):** build surrogate (fidelity TBD) |
| DQ8 | **Range reset** between cohorts: config export/restore + a scripted "clean the exercise account / inert file / drill rules" step — acceptable without VM checkpoints? | OPEN |

## 10. Prep task list

| # | Task | Owner | Status |
|---|---|---|---|
| DT1 | Tracker (this file); map assets; design frame | Claude | **DONE (v1)** |
| DT2 | Operator answers DQ1–DQ8; log decisions | Operator | TODO |
| DT3 | White Team truth log (DP4) + per-inject LIVE/SIM decision | Claude | **DONE (v1)** → `WHITE_TEAM_DESIGN.md` §1–3 |
| DT4 | Detection key: 12 moves → existing Splunk/Scribbler/SSM alert or gap (DP5) | Claude | **DONE (v1)** → `WHITE_TEAM_DESIGN.md` §4 |
| DT5 | Surrogate CSTR + eng-station build, if DP2 approved | Claude (offline) | TODO |
| DT6 | Drill firewall posture + backup/rollback, if DP3 approved | Operator-supervised | TODO |
| DT7 | 12 inject artefacts (real steps or labelled SIM packets, hashed) | Claude | TODO |
| DT8 | Facilitator run-sheet (minute-by-minute White), role/room layout, dry run | Claude + Operator | TODO |
| DT9 | Participant packs: Red step cards, Blue workflow+log, scoring sheets | Claude | TODO |

## 11. Decision log

| ID | Date | Scope | Decision | Rationale |
|---|---|---|---|---|
| DD1 | 2026-10-19 | Drill | This workbook is prepared as a **facilitated Red/Blue/White drill**, not an M-series familiarisation lab; deliverables = White inject pack + detection key + run-sheet, not an ANSWER_BOOK per table | Workbook nature |
| DD2 | 2026-10-19 | Drill | **Drill-specific device config is allowed** (change + save, backup-first) on in-scope devices to facilitate the drill; does not lift rule 13 for L2/L1 | Operator, 2026-10-19 |
| DD3 | 2026-10-19 | Drill | **Target experience = a real-world feel of attacking and defending.** Maximise LIVE hands-on-keyboard: Red runs real tools against real/surrogate targets; Blue investigates on the real Splunk/SSM/NMS/Scribbler consoles. Paper-only SIM is reserved for the few actions that genuinely cannot be real (live privilege-escalation exploit, live alarm suppression on a safety function). Everything else — including the OT half — is made tactile via in-scope surrogates (DP2) | Operator, 2026-10-19 |
| DD4 | 2026-10-19 | Drill | **Full ~4.5 h / half-day format** (answers DQ1): all 12 injects, full G0–G14 gate cadence, proper AAR | Operator |
| DD5 | 2026-10-19 | Drill | **One Red + one Blue** (~8 each), trainer = White Team / Exercise Director; single linear drill on one range (answers DQ2) | Operator |
| DD6 | 2026-10-19 | Drill | **Capstone level** (participants did M1/M2; answers DQ3): Red gets objective cards + freedom, Blue works the real consoles themselves, minimal scaffolding | Operator |
| DD7 | 2026-10-19 | Drill | Per DD3, **build in-scope surrogates** for the Engineering Station and CSTR (resolves DQ4, DQ7 toward "build, not SIM"); only the two un-realisable techniques stay paper-SIM | Claude, from DD3 |
| DD8 | 2026-10-19 | Drill | **Red starts on Kali (L5) and earns the RAC foothold** (new Stage 0) rather than starting on RAC — adds the enterprise initial-access step; RAC has UF+Sysmon so it's fully instrumented | Operator |
| DD9 | 2026-10-19 | Drill | **SSM dropped for the drill; Zeek + Suricata** provide network visibility on the drill path (SPAN of L5 + FW-South transit). Richer than SSM and on the IT/DMZ path where the action is (answers DQ6) | Operator |
| DD10 | 2026-10-19 | Drill | **Stage-based flag model** (CTF-style): each stage/gate = one concrete flag; Red captures it, Blue mirror-detects + may deny it. Participant-driven; branch logic falls out of flag capture/denial. Operator maps Red/Blue options → flags | Operator |
| DD11 | 2026-10-19 | Drill | **Historian has a credential** (DQ5) → Stage 8/12 run live against real `L3H1_Historian` 192.168.30.10; operator to set/confirm the password in the credentials file | Operator |
| DD12 | 2026-10-19 | Drill | **One highlighted "golden path" is fully planned/staged/flagged** (`GOLDEN_PATH.md`): Kali→foothold→**PtH→Domain Admin**→DC honeyfile `password.txt`→**SINEC INS RADIUS user**→open DMZ→OT on the boundary→**EWS→Modbus write→light glows**. Other Red routes left open for students. Four flags GP-1..GP-4. We plan only this path now | Operator |
| DD13 | 2026-10-19 | Drill | **GP-3/GP-4 run on an ISOLATED drill segment with surrogates** (surrogate OT-boundary RADIUS-backed by the *real* INS, surrogate EWS, drill Modbus light), **not** the real SC646-2C / real L2-L1. Opening the real OT-FW DMZ→L2 would bridge students into the live PLC/IED/**SIS** domain — outside the rule-13 OT-FW exceptions and an unacceptable safety risk ([[trainee-wifi-ap-project]]). **PROPOSED — awaiting operator confirmation (GP open #2)** | Claude (safety) |

## 12. Changelog

- 2026-10-20: **Range staging started.** Read-only check of `L4H1_RAC` (was standalone WORKGROUP,
  active NIC on Hyper-V vSwitch **WAN** = L5 10.5.20.0/24, gw .254). Kali VM `L4H1_Attacker` NIC was
  disconnected; **operator attaches it to vSwitch WAN + configures Kali** (SSH not present by
  default). **Joined RAC to `np.local`** (DNS→DC 10.1.20.17, `NP\Administrator`, rebooted, verified
  PartOfDomain=True + SecureChannel=True; audit `drill.rac-domain-join`). This makes RAC a realistic
  domain-member foothold for GP-0/GP-1 and gives Blue DC-side logon telemetry. DQ5 confirmed done
  (`L3H1_Historian/Administrator` password is set). Runner: scratchpad `join_rac_domain.py`.
- 2026-10-20: **Kali staged + reachable.** `L4H1_Attacker_Kali` 10.5.20.50/24 on vSwitch WAN (same as
  RAC), SSH enabled (kali/kali), host key pinned `SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA`
  (ssh-rsa), inventory updated. Tooling: nmap 7.99, netexec/nxc, impacket, responder, evil-winrm.
  Targeted reachability from Kali (read-only): **DC 10.1.20.17** 88/389/445/3389 open (PtH path works);
  **MSSQL** 1433/3389 open but **445 filtered**; **RAC** 3389/5985 open, **445 filtered** (domain-profile
  firewall after join); **INS** 22/443 open. L5→DMZ confirmed traversable. **Open item (GP-0 seed):**
  445 filtered to MSSQL ⇒ direct SMB `secretsdump` from Kali to the seed host won't work — seed the
  cached DA hash on **RAC itself** (Red already owns it; cleanest) or reach MSSQL via pivot/1433.
- 2026-10-20: **Phishing initial-access variant adopted** (operator). GP-0 becomes: SMTP phish →
  victim (White clicks) → reverse shell on RAC → elevate → dump a **seeded privileged service-account
  hash** from RAC → PtH to DC → use DA to reach **NMS/MaintServer** → honeyfile `password.txt` (moved
  from DC to MaintServer) → INS → OT → light. Mail server: **hMailServer** on `L4H1_MailServer`
  recommended (operator deploying). **Stage-2 recon (read-only) validated the PtH chain:** RAC =
  Win Server 2022, `NP\Domain Admins` are local admins, **RunAsPPL off / Credential Guard off /
  Defender RTP off / Trellix enforcement modules stopped** ⇒ LSASS extraction viable; MaintServer
  192.168.30.11 reachable from Kali on 445/5985/3389/443/8443 and DA is local admin there ⇒ PtH hop
  works. Durable-hash design: run a **service/scheduled task on RAC as a privileged domain account**
  so its NT hash stays resident across reboots. The live `nxc` PtH auth proof was **blocked by the
  auto-mode classifier** (credential-attack tooling) — operator to run the one-line confirm or grant
  a permission rule. Scripts: scratchpad `rac_recon.ps1`, `pth_nms_test.py`.
- 2026-10-20: permissions cleared (operator added `PowerShell`/`Skill` allow + manual approval mode).
  **Pass-the-hash into NMS proven LIVE:** `nxc smb`/`nxc winrm` to MaintServer 192.168.30.11 with the
  DA NT hash → `(Pwn3d!)` on both (admin). Evidence in `cyberdrill-artefact/STAGE2_PTH_CONFIRM.txt`.
  GP-1→GP-2 destination leg confirmed. Next: durable seed (service account resident on RAC) + live
  extract→PtH chain, then GP-2 honeyfile on MaintServer.
- 2026-10-20: **Seed built** — `np\svc_backup` (Domain Admin) on the DC + resident `LabBackupAgent`
  task on RAC (hash in LSASS, survives reboot). Scripts now kept under
  `cyberdrill-artefact/scripts/` (operator wants them compilable with the guide). **Extraction
  attempt hit a blocker:** `comsvcs` LSASS dump *creates* (50 MB) but **Trellix ENS quarantines/
  deletes it** before it can be read (corrects the earlier "AV permissive" read — ENS on-access IS
  active). Also **RAC SMB 445 is filtered** from MC01 + Kali, forcing the slow WinRM transfer. Both
  logged with fixes in `cyberdrill-artefact/BLOCKERS.md` (operator to add a Trellix exclusion on RAC
  ± open 445). Everything else on GP-0→GP-2 is proven; extraction will complete once AV is excluded.
- 2026-10-20: **Mail server live** (operator): hMailServer 5.7.1, `mail.np.local`, victim mailbox
  **RemoteIT** in Thunderbird on RAC; mail→Splunk `index=mail`. **GP-0 phishing built + delivery
  proven:** from Kali, header-`From: admin@mail.np.local` with an external envelope is **ACCEPTED
  unauthenticated** (no config loosening needed) — so the lure displays as the internal NP admin.
  Built `cyberdrill-artefact/gp0-phish/` (lure email sender, HTA, PS reverse shell), deployed to
  Kali `/home/kali/drill/`, styled preview delivered to the mailbox. **Click→shell pending only B1**
  (Trellix exclusion on RAC so the PS revshell runs). Privilege resolved: `RemoteIT` is just the
  mailbox; White logs into RAC's Windows session as a **privileged domain account**, so the shell is
  admin-context (no priv-esc; dumps the resident `svc_backup` hash directly). Reusable Kali helpers:
  `kali_run.py`, `deploy_phish.py`.


- 2026-10-19: Tracker created. Parsed the full workbook (13 §, 12 injects, 15 gates, ATT&CK
  matrix, scoring). Mapped all 11 named assets to real lab assets (§5) and found the LIVE
  (L5→DMZ/L3) vs SIM/surrogate (L2/L1/L0) split at FW-South. Logged DD1–DD2, proposals DP1–DP5,
  gaps DG1–DG8, questions DQ1–DQ8. Awaiting operator on DQ1–DQ8 before the scenario build.
