# Lab Activity Preparation Prompt (reusable)

Paste the block below into a new conversation. Replace `<MODULE>-<SESSION>` and the workbook
path with the activity you want to prepare. Example: `M1-S2`, pointing at
`Lab-Modules/Module_1_Workbook__...docx`.

---

```
I want to prepare lab-activity <MODULE>-<SESSION> from the workbook at
`Lab-Modules/<WORKBOOK FILE>`. Work through the activity end-to-end with me:
plan how the trainer and students actually run it, build any synthetic
teaching materials (captures, screenshots, cards), and produce the answer
book. We did M1-S1 the same way; use it as a template.

Context you need before touching anything:

1. Read `CLAUDE.md` in the project root. Every rule there applies, especially
   rule 13 (L2 and below are out of scope for Claude and the Lab Console).
2. Read every memory in `.claude/projects/.../memory/`, in particular
   `lab-activities-planning.md`, `no-vm-checkpoints-licensing.md`,
   `phase-reports-and-visible-browser.md`, `trainee-wifi-ap-project.md`,
   `nms-onboarding-project.md`.
3. Read `config/inventory.yaml` for the real DMZ/L3/L4/L5 facts. L2 and below
   are deliberately not in the inventory; the real MACs for L1/L2 live in
   the saved outputs at `%LOCALAPPDATA%\LabConsole\nms-onboarding\...` and
   `Backups\`. Use those, not the architecture drawing.
4. Read the M1-S1 artefacts as the working template:
   - `Lab-Modules/M1-S1/LAB_ACTIVITIES_TRACKER.md` (per-session tracker)
   - `Lab-Modules/M1-S1/CLASSROOM_PLAN.md` (minute-by-minute delivery plan)
   - `Lab-Modules/M1-S1/ANSWER_BOOK.md` (per-table: student steps, teaching
     emphasis, expected answer)
   - `tools/lab-pcap/` (synthetic capture generator; `.venv` already set up)
5. Read the workbook section for `<MODULE>-<SESSION>` end-to-end before
   proposing anything.

The lab, in one line: workgroup Hyper-V OT/ICS training lab at Ngee Ann
Polytechnic, Siemens stack. Trainer Rack (DMZ-Host-1/-2, L4-Host-1, plus a
Trainer Rack with L1/L0 physical devices) + 8 Tabletop Trainee Kits.
Delivery assumptions already locked (don't re-derive):
  - 1 trainer, ~16 students, 2 per kit, 8 kits = SSID/VLAN 101-108.
  - Session length: whatever the workbook says (M1 sessions are 120 min).
  - AI step uses a web-based AI chat on BYOD; lab IPs may be pasted; no
    credentials.
  - Rack facts come from the real lab (reality wins over the drawing).
  - No Hyper-V checkpoints of lab VMs (voids licenses).
  - SIS island must stay silent in any synthetic capture: no 192.168.2.*
    traffic anywhere.

Create a new folder `Lab-Modules/<MODULE>-<SESSION>/` and put every
deliverable for this activity inside it. The folder is this activity's
single source of truth.

Deliverables (produce in this order; stop and ask when blocked):

A. Session tracker: `Lab-Modules/<MODULE>-<SESSION>/<SESSION>_TRACKER.md`.
   First thing you create. Keep it current as decisions land. Sections:
     1. Status at a glance (one row per phase, next step)
     2. Sources (workbook, drawing, inventory, saved outputs, memories)
     3. Standing constraints (CLAUDE.md rule 13; no VM checkpoints; class
        shape; SIS silent; D11 familiarisation unless the workbook says
        otherwise)
     4. What the workbook asks for (summary table of the parts)
     5. Terms-to-lab mapping (workbook names -> real rack/kit assets)
     6. Observations and gaps (G1, G2, ...)
     7. Proposals, not decided (P1, P2, ...)
     8. Open questions (Q1, Q2, ... with status: OPEN / DECIDED / RESOLVED)
     9. Prep task list (T1, T2, ... with Owner + Status)
    10. Build status, if any synthetic artefact is needed
    11. Decision log (D1, D2, ... with Date, Scope, Decision, Rationale)
    12. Changelog
   Status tags everywhere: OPEN / PROPOSED / DECIDED / TODO / IN PROGRESS /
   DONE. Decisions and questions keep increasing IDs across sessions
   (lookup should jump straight to Dxx).

B. Classroom plan: `Lab-Modules/<MODULE>-<SESSION>/CLASSROOM_PLAN.md`.
   Written from both the trainer's and the student's seat. Must include:
     - A room layout sketch
     - Materials: what exists, what's still to produce, who owns each
     - Pre-class checklist for the trainer (T-7 days, T-1 day, T-30 min)
     - A minute-by-minute trainer run-sheet with [SAY] and [DO] lines
     - Draft content of any student-facing cards referenced by the plan
     - A time-lapse of what one pair sees over the full session
     - Failure modes and what the trainer does when they fire
     - Open logistical questions (AI access per kit, evidence collection,
       kit reset, etc.) with a default proposal for each

C. Synthetic materials, if the activity needs them. For captures use the
   generator at `tools/lab-pcap/`:
     - Spec file under `tools/lab-pcap/spec/<MODULE>-<SESSION>.yaml`
     - Use real protocol stacks on 127.0.0.1 (snap7, libiec61850, pymodbus,
       asyncua, pysnmp). For protocols where libiec61850's connect rejects
       a proxy, use the Npcap-loopback capture helper in
       `tools/lab-pcap/labpcap/loopcap.py`.
     - Pre-pad PROFINET so the APDU trailer sits at the final 4 bytes of
       the Ethernet payload (eth() pads to 60 and would otherwise push the
       trailer out).
     - Validation gate before you declare done: `tshark` must report ZERO
       malformed frames and the expected protocols in the hierarchy.
     - Record the SHA-256 in the tracker and in the answer book header.
     - Make periodic traffic non-uniform: jitter, occasional missed cycles,
       variable query mixes.

D. Answer book: `Lab-Modules/<MODULE>-<SESSION>/ANSWER_BOOK.md`. One
   section per workbook table. Every section has three subsections, in
   this exact order:
     1. "What students actually do" - the concrete clicks and keystrokes
        on the kit, including which Wireshark menu, which filter, etc.
     2. "Teaching emphasis" - 2 or 3 bullets on what the trainer wants
        them to walk away understanding.
     3. The expected answer table.
   Every expected answer must be verified against the capture (if the
   session has one) with tshark before writing it down. Numbers must be
   real, not predicted.

E. Student materials referenced by the classroom plan: walk-through card
   (self-guided), Wireshark/tool cheat sheet, asset-card pack (text that
   Claude drafts, photos/screens the operator supplies).

Working style:

- Make reasonable defaults and keep going; flag what's genuinely blocked.
  Do not ask questions you can answer from the files above.
- When a judgement is substantive (naming a planted asset, choosing a
  flow story, picking the AI-trap claim), present it as a proposal in the
  tracker and surface the question in your message so the operator can
  redirect.
- Record decisions as they land. A decision in a chat message that doesn't
  make it to the tracker's Decision Log doesn't count.
- Pedagogical focus is familiarisation unless the workbook says otherwise
  (M1 is a first-contact course). Materials should explain, not just
  instruct.
- The classroom plan is for 1 trainer. If the plan needs an assistant,
  the plan is wrong - rework it.

Start by reading the files above, then propose the tracker's first draft
(sections 1-7 populated, Questions as OPEN, Decisions log empty) and tell
me what you need from me to proceed to section 8 and beyond.
```

---

## Tips when you paste it

- **Point at the right workbook.** `Lab-Modules/` holds one `.docx` per module.
  M1 covers assessment (S1-S4). M2 is Asset & Configuration Management (sessions
  not yet checked). Point at the right file so Claude doesn't guess.
- **Reuse decisions across sessions when they apply.** D2 (class shape), D5 (AI
  tool policy) and D12 (reality wins over the drawing) apply to every M1 session.
  You can tell Claude "D2, D5 and D12 from M1-S1 also apply here" in the paste.
- **Session-specific memory.** When Claude finishes the first phase of a new
  activity, ask it to write a small memory entry so future sessions know the
  tracker lives in `Lab-Modules/<MODULE>-<SESSION>/`.
- **Already in flight.** M1-S2 has its own in-progress tracker at
  `Lab-Modules/M1-S2/M1_S2_TRACKER.md` with the ID prefix `S2-`.
