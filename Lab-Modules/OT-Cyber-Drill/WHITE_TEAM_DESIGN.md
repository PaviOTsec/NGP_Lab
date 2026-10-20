# OT Cyber Drill — White Team Scenario Spine & Detection Key

**White Team only. Do not hand to Red or Blue.** This is the ground truth that ties every inject
to its real target, its Red action, its LIVE/SIM/surrogate label, and the exact Blue detection on
our real consoles. The inject cards, timeline, scoring key and AAR all derive from this file, so
they cannot disagree. Modelled on the M2-S2 `STAGING_LOG.md` pattern.

Decisions in force: DD1–DD7 (see `DRILL_TRACKER.md`). Format: full half-day, one Red + one Blue,
White = trainer, capstone participants, maximise LIVE/hands-on (DD3), build surrogates (DD7).

---

## 0. The range at a glance

```
 RED seat (L5)                 BOUNDARY            BLUE seats (DMZ consoles)
 L4H1_RAC 10.5.20.10  ──FW-North──► MaintServer ──FW-South──► [OT SURROGATES]
 (exercise account)   10.4.20.254   192.168.30.11  10.1.20.254   eng-station + CSTR
                                    (real pivot)    (drill posture) (we build, in-scope)
                           │                                   │
                           └──────── telemetry ────────────────┘
        Splunk 10.1.20.15 · Scribbler 10.1.20.13 · SINEC NMS 192.168.30.11 · SSM 10.1.20.18
```

- **LIVE zone (real kit, real detection):** RAC → FW-North → MaintServer → FW-South. Everything
  here is a real machine the console already drives, feeding the real SIEM.
- **Surrogate OT zone (we build, in-scope, rule-13-safe):** an **Engineering-Station surrogate**
  and a **CSTR process simulator** stood up on an in-scope VM (candidate: `DMZH2_Spare`, or a
  dedicated drill VM on DMZ-HOST-2), reachable *through* FW-South so the boundary crossing is
  real. Real protocol stacks (snap7 / pymodbus), no L2/L1 device touched. This is what lets Red
  actually "change a setpoint and watch the trend move."
- **Paper-SIM (only two):** INJ-04 (privilege-escalation exploit) and INJ-10 (alarm suppression
  on a safety function) — delivered as labelled evidence packets, never executed live.

## 1. LIVE / SIM / surrogate decision per inject

| Inject | ATT&CK (ICS) | Real target | Red does (hands-on) | Label |
|---|---|---|---|---|
| INJ-01 Remote access | T0822 External Remote Services | MaintServer via FW-North, exercise acct | RDP/WinRM in from RAC | **LIVE** |
| INJ-02 Benign execution | T0807 Command-Line | MaintServer | run one approved command (e.g. `whoami /all`, `systeminfo`) | **LIVE** |
| INJ-03 Repeat account use | T0859 Valid Accounts | MaintServer | second sign-in with same acct | **LIVE** |
| INJ-04 Privilege challenge | T0890 Exploit for Priv-Esc | — | *nothing live* — White delivers a labelled attempt event | **PAPER-SIM** |
| INJ-05 Maintenance-like file | T0849 Masquerading | MaintServer | drop an inert file w/ known hash on an authorised path | **LIVE** |
| INJ-06 Named discovery | T0846 Remote System Discovery | eng-station surrogate (through FW-South) | one bounded `nmap -sT` of the named host only | **LIVE (surrogate)** |
| INJ-07 Engineering-path attempt | T0886 Remote Services | eng-station surrogate | one connection attempt across FW-South | **LIVE (surrogate) / BLOCK point** |
| INJ-08 Read-only process view | T0801 Monitor Process State | Historian (if pw set) or CSTR surrogate historian | read a batch trend | **LIVE or surrogate** (DQ5) |
| INJ-09 Benign isolated connection | T0885 Commonly Used Port | inside the range | one pre-approved connection, owner recorded | **LIVE** |
| INJ-10 Alarm-integrity | T0878 Alarm Suppression | — | *nothing live* — White delivers a missing-alarm SIM sequence | **PAPER-SIM** |
| INJ-11 Bounded CSTR change | T0836 Modify Parameter | **CSTR surrogate** | after G11, change ONE non-safety setpoint; watch trend | **LIVE (surrogate)** |
| INJ-12 Historian discrepancy | T0832 Manipulation of View | CSTR surrogate historian | — White injects a trend/record conflict | **LIVE (surrogate)** |

## 2. Per-inject detail — Red action, Blue detection on the real stack, gate, branches

For each: **Red** (what the red seat types), **Signal** (what it leaves), **Blue** (where they
find it on *our* consoles + which existing alert), **Adjudicate**, **Branch hooks**.

### INJ-01 — Remote access (T+10, G1) · LIVE
- **Red:** from `L4H1_RAC`, RDP (or WinRM) to `MaintServer` 192.168.30.11 as the exercise
  account `np\drill-svc` (created for the drill, non-privileged).
- **Signal:** Windows **4624** logon (type 10 RDP / type 3 WinRM) on MaintServer → UF → Splunk
  `index=wineventlog`. FW-North **allow is unlogged** (DG3) — so the firewall will *not* show it
  unless we enable allow-logging for the drill (DP3 option).
- **Blue:** Splunk search `index=wineventlog host=DMZH2MAINT EventCode=4624 | \`lab_logon_fields\``;
  verify the account, source IP (10.5.20.10) and that no change ticket authorises it. Existing
  **LAB** logon panels on the Lab Security dashboard show it.
- **Adjudicate:** Blue confirms ticket/account/source → full detect credit. If Blue **disables
  `drill-svc`** here → record **BLOCK**, Branch B, defensive credit; later injects become SIM
  counterfactuals.
- **Teaching:** the allow doesn't appear in firewall logs — you catch initial access **host-side**.
  That asymmetry is a deliberate telemetry lesson.

### INJ-02 — Benign execution (T+25, G2) · LIVE
- **Red:** on the MaintServer session, run one approved command (`whoami /all`, `systeminfo`, or
  `net group`).
- **Signal:** **Sysmon EventCode 1** (process create) + 4688 → Splunk `index=sysmon` /
  `index=wineventlog`. Full command line captured (lab Sysmon = full ProcessCreate).
- **Blue:** `index=sysmon host=DMZH2MAINT EventCode=1 | table _time User ParentImage Image
  CommandLine`; correlate the process back to the INJ-01 session (same user/logon ID).
- **Adjudicate:** credit for correlating host execution to the session, not just seeing a process.

### INJ-03 — Repeat account use (T+40, G3) · LIVE
- **Red:** sign in a second time (new session) with `drill-svc`.
- **Signal:** second **4624**, distinct time/logon-ID.
- **Blue:** same logon search; assess whether this is continued/persistent access vs a one-off.
- **Adjudicate:** Blue states "valid-account reuse, access still live" with both timestamps.

### INJ-04 — Privilege challenge (T+55, G4) · **PAPER-SIM**
- **Red:** nothing live. **White** hands Blue a labelled evidence packet `EVID-INJ04-SIM`: a
  mocked host event *suggesting* an elevation attempt, with **no proof of elevated privilege**.
- **Blue:** must record "attempt observed, success **not** demonstrated" — the core
  evidence-discipline test. Looking for a real 4672/privileged logon in Splunk should come up
  **empty**, which is the point.
- **Adjudicate:** full credit only if Blue distinguishes attempt from success and does **not** log
  it as a confirmed compromise. (Red scoring: SIM earns evidence-discipline points only — never
  live-access credit.)

### INJ-05 — Maintenance-like file (T+70, G5) · LIVE
- **Red:** drop an **inert** file (e.g. `maint_update_q4.ps1` that only echoes) on an authorised
  MaintServer path; record name/path/hash in §3.
- **Signal:** **Sysmon EventCode 11** (FileCreate) → Splunk; hash recorded by White.
- **Blue:** `index=sysmon host=DMZH2MAINT EventCode=11 TargetFilename=*maint_update*`; check the
  hash/provenance — name says "maintenance", provenance says "dropped by the drill session."
- **Adjudicate:** credit for checking hash + provenance (masquerading), not just spotting a file.

### INJ-06 — Named discovery (T+85, G6) · LIVE (surrogate)
- **Red:** from MaintServer, one **bounded** `nmap -sT -Pn -p 102,502,80,443 <ENG_SURROGATE>` —
  the *named* host only, no sweep.
- **Signal:** crosses FW-South → **deny/allow logged → Scribbler → Splunk `index=netdev`**. The
  connection attempts hit Sysmon network events (EventCode 3) on MaintServer too.
- **Blue:** `index=netdev sourcetype=paloalto` for the source/destination/scope; existing
  **LAB NET** sweep/scan alert fires if the rate crosses threshold. Confirm the target is
  outside the work order.
- **Adjudicate:** BLOCK if Blue has already contained; else record scope. **Freeze** if Red
  scans anything beyond the named host (scope discipline is scored).

### INJ-07 — Engineering-path attempt (T+100, G7) · LIVE (surrogate) · **the BLOCK showcase**
- **Red:** one connection attempt MaintServer → eng-station surrogate across **FW-South**
  (e.g. S7/TCP 102 or RDP).
- **Signal:** with the **drill firewall posture** (DP3) this is where allow-vs-deny is real. If
  Blue contained → **FW-South deny → Scribbler → `index=netdev`** (LAB NET "unauthorized
  connection through firewall" / deny). If still open → allow + host-side evidence on the
  surrogate.
- **Blue:** pull the FW-South decision from `netdev`; this is the moment firewall telemetry pays
  off (unlike INJ-01). Trace the boundary; recommend/confirm containment with rollback.
- **Adjudicate:** **denied → record BLOCK, switch to Branch B** for the OT stages (they become
  SIM counterfactuals). Allowed → continue Branch A into the surrogate.

### INJ-08 — Read-only process view (T+115, G8) · LIVE or surrogate
- **Red:** read a batch trend — either the real **Historian** 192.168.30.10 (if the operator sets
  a password, DQ5) or the **CSTR surrogate's historian view**. No controller query.
- **Signal:** read audit on the Historian/surrogate; Sysmon network event to it.
- **Blue:** identify what information was exposed (batch PB-2027-091 data) and that it was
  read-only. 
- **Adjudicate:** credit for naming the exposed data and confirming read-only (no write).

### INJ-09 — Benign isolated connection (T+145, G9) · LIVE
- **Red:** one pre-approved connection inside the range to a recorded destination/port/owner
  (the "commonly used port" C2 stand-in — benign, no real beacon).
- **Signal:** network-flow record (Sysmon EventCode 3 / netdev).
- **Blue:** validate destination and owner; flag the destination/owner mismatch.
- **Adjudicate:** credit for owner validation; **Freeze** on any unexpected external route.

### INJ-10 — Alarm-integrity (T+160, G10) · **PAPER-SIM**
- **Red:** nothing live. **White** delivers `EVID-INJ10-ALARM`: a SIM alarm timeline in which an
  **expected alarm is absent**, plus the **independent operator record**.
- **Blue:** must notice the missing alarm *and* seek **independent verification** rather than
  trusting the HMI — state the uncertainty. No live suppression is ever performed (safety).
- **Adjudicate:** credit for independent cross-check + stating uncertainty.

### INJ-11 — Bounded CSTR change (T+180, G11) · LIVE (surrogate) · **the tactile climax**
- **Red:** **only after Exercise Director + Safety approve G11**, make ONE non-safety change on
  the **CSTR surrogate** — e.g. nudge the **agitation setpoint** (never a safety parameter) via a
  snap7/Modbus write. Watch the **live trend move**.
- **Signal:** before/after values in the surrogate's change audit; the trend visibly shifts.
- **Blue:** detect the parameter change (surrogate audit / trend), verify whether it was approved,
  and make the **process-protection / batch-risk** decision — recommend pause/degrade, advise
  Gold. This is the process-protection score.
- **Adjudicate:** the change is pre-approved and **rolled back** to baseline after. Credit Blue
  for protecting the process, not for "stopping" a pre-authorised action.
- **Rule 13:** the real pharma cell is **never** touched. The surrogate is the only thing that
  moves.

### INJ-12 — Historian discrepancy (T+200, G12) · LIVE (surrogate)
- **Red:** nothing (or a read). **White** injects a **trend-vs-operator-record conflict** into the
  surrogate historian.
- **Blue:** reconcile the training trend against the independent operator record and **advise
  OT Ops / Gold on batch disposition** (release / hold / investigate PB-2027-091).
- **Adjudicate:** credit for reconciliation + a defensible batch recommendation.

### G13 — Containment close (T+220) · G14 — Recovery (T+250)
- **Blue:** containment recommendation with owner/approval/rollback recorded; then verify trusted
  baselines — exercise account removed, inert file removed, CSTR surrogate restored to baseline,
  eng-station surrogate and Historian views verified, evidence preserved + hashed.
- **White:** confirm the real controller/SIS were never in scope (truth log), Safety Officer
  attestation, close or extend.

## 3. White truth log (fill on the day)

| Inject | Label | Artefact / command | Hash (if file) | Fired alert / panel | Observed time | Branch |
|---|---|---|---|---|---|---|
| INJ-01 | LIVE | RDP `drill-svc` RAC→Maint | — | LAB logon | | |
| INJ-02 | LIVE | `whoami /all` on Maint | — | Sysmon EC1 | | |
| INJ-03 | LIVE | 2nd sign-in | — | LAB logon | | |
| INJ-04 | SIM | EVID-INJ04-SIM packet | n/a | — (must stay empty) | | |
| INJ-05 | LIVE | inert file drop | `<sha256>` | Sysmon EC11 | | |
| INJ-06 | LIVE | nmap named host | — | LAB NET sweep | | |
| INJ-07 | LIVE | FW-South crossing | — | LAB NET deny | | |
| INJ-08 | LIVE/surr | historian read | — | read audit | | |
| INJ-09 | LIVE | approved connection | — | netdev/Sysmon EC3 | | |
| INJ-10 | SIM | EVID-INJ10-ALARM packet | n/a | — | | |
| INJ-11 | surr | setpoint change | — | surrogate audit | | |
| INJ-12 | surr | historian discrepancy | — | surrogate audit | | |

## 4. Detection key — 12 moves → existing alert or gap (DP5)

| Move | ATT&CK | Our telemetry | Existing alert / search | Gap? |
|---|---|---|---|---|
| 01 Remote access | T0822 | wineventlog 4624 (Maint UF) | LAB logon panels; new LAB "remote logon from L5" (to add) | allow unlogged on FW-North (DG3) |
| 02 Execution | T0807 | sysmon EC1 (Maint) | ESCU cmdline detections; ad-hoc search | — |
| 03 Valid accounts | T0859 | wineventlog 4624 x2 | LAB logon; LAB brute-force if they fat-finger | — |
| 04 Priv-esc | T0890 | **none (SIM)** | — (absence of 4672 is the tell) | intentional |
| 05 Masquerading | T0849 | sysmon EC11 | ad-hoc hash/provenance search | — |
| 06 Discovery | T0846 | netdev (FW-South), sysmon EC3 | LAB NET sweep/scan | SSM won't see it (DG4) |
| 07 Lateral movement | T0886 | netdev deny (FW-South) | LAB NET "unauthorized connection through firewall" | needs drill posture (DP3) |
| 08 Collection | T0801 | historian/surrogate read audit | ad-hoc; new panel | historian pw (DQ5) |
| 09 C2 port | T0885 | netdev / sysmon EC3 | LAB NET; ad-hoc flow search | — |
| 10 Alarm suppression | T0878 | **none (SIM)** | independent operator record | intentional |
| 11 Modify parameter | T0836 | surrogate change audit + trend | new surrogate alert (to build) | surrogate only (rule 13) |
| 12 Manipulation of view | T0832 | surrogate historian audit | reconciliation vs operator record | surrogate only |

**Build list that falls out of this (feeds DT5–DT7):**
1. CSTR surrogate (process model + snap7/Modbus server + live trend + change audit + historian
   view) and an eng-station surrogate, on an in-scope VM reachable through FW-South.
2. Drill firewall posture on FW-South/FW-North (DP3): authorised exercise path allowed, everything
   else denied+logged so INJ-06/07 and Blue containment are real. Backup-first, one named snapshot.
3. Two SIM evidence packets: `EVID-INJ04-SIM`, `EVID-INJ10-ALARM`.
4. Exercise account `np\drill-svc` (non-privileged) + change-ticket paperwork for the authorised
   actions (so Blue can separate authorised from unauthorised).
5. One new Splunk LAB alert "remote logon from L5 to L3 pivot" and a CSTR-change panel; reuse
   LAB NET deny/sweep as-is.
6. Historian password (operator, DQ5) if INJ-08/12 are to be fully LIVE rather than surrogate.
