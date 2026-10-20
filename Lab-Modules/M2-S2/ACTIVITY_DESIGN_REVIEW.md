# M2-S2 — Activity Design Review

Is Session 2 worth running as written, what does it teach, and how do the trainer and students
interact? Decisions that come out of this review are logged in `M2_S2_TRACKER.md` (§11). The
planted deviations and how each is caught are in `STAGING_LOG.md`.

Status: **PROPOSED**. Awaiting operator review (M2S2-Q1, Q2).

---

## 1. Verdict

**Worth running, and it is the payoff of Session 1.** It teaches the habit that separates
monitoring from alarm-chasing: *a deviation is not an incident*. You detect it, explain it,
check it against what was authorised, and dispose of it with an owner.

As written it has the same problem as Session 1: too many tables over the same few items. Five
of its seven tables are keyed by "the deviation", so pairs write the same 4–6 deviations five
times. The classification, where the learning is, comes last and gets rushed.

## 2. Progression

| Session | Question | Compared against |
|---|---|---|
| M1-S1 | "What is this device?" | nothing (first look) |
| M1-S2 | "Is this traffic normal?" (T3, baseline vs the S7 write) | a traffic baseline |
| M2-S1 | "What do we know, how do we know it, how sure are we?" | the documentation (diagram vs wire) |
| **M2-S2** | **"What changed, and does it matter?"** | **our own baseline, over time** |

M2-S1's three buckets (documented & seen / documented, not seen / seen, not documented) become
M2-S2's change types applied over time. "Undocumented" in S2 is S1's "seen, not documented"
bucket that nobody has resolved yet.

Three seams to fix (tracker G2, G3, G9):
1. **Repetition:** re-running all of S1 by hand. Keep the method, script the typing.
2. **Method mismatch:** the workbook's S2 scan differs from S1. Use S1's standard scan, unchanged.
3. **SINEC blind spot:** NMS/SSM don't see the kits. Put one rogue (R1) where they do look.

## 3. Tables: 7 → 3 plus a checklist

| Refined | Covers | What changes |
|---|---|---|
| **Pre-flight box** | W2.1 | 4 lines: file present, hash matches the S1 log. Also prepares S4's integrity work |
| **T1 Baseline vs Now** | W2.2 + W2.3 | Pre-printed with the pair's S1 rows (IP **and** MAC, open ports). Students add the "now" value and a change type; new rows at the bottom. The raw `-oA`, `ndiff` and capture files are the Re-Discovery evidence |
| **T2 Deviation Case Sheet** (one per deviation) | W2.4 + W2.5 + W2.6 | Left to right in reasoning order (below) |
| **T3 Handover** | W2.7 | 5 sentences: what changed, how detected, significance, confirmed rogues, actions + owners. AI drafts it from the case sheets; students correct it (covers "≥ 1 AI claim corrected") |
| Evidence log | — | `Get-ChildItem … \| Get-FileHash \| Export-Csv`, not typed |

**T2 Deviation Case Sheet** (half a page each):

| Field | Prompt |
|---|---|
| Deviation | One line, from T1 |
| Change type | New / Missing / Modified / Undocumented |
| Wireshark says | Filter used + what it showed |
| Nmap / host says | `ndiff` line or PowerShell output |
| SINEC says | Visible? first seen? alert? asset context? (or "not monitored here" — that's a finding too) |
| Change calendar says | CR number, or "no entry" |
| Hypothesis | What I think happened |
| Classification | Rogue / Legitimate but undocumented / Maintenance / Unresolved |
| Rationale | Which two pieces of evidence decided it |
| Disposition, owner, due | From the definitions card's owner list |

## 4. How the session teaches

- **One deviation per classification, plus a trap** (STAGING_LOG §2). Every classification is
  reachable, and one of them can only be found by joining two others.
- **Detection before authorisation.** The change calendar is handed out at checkpoint 1, *after*
  pairs have their diff. They detect without bias, then classify against evidence.
- **No single tool catches everything** (STAGING_LOG §5 matrix). The matrix is the debrief slide
  for reflection Q1.
- **Diffs keyed on IP hide replacements.** K4 looks like "no change" to Nmap; only the baseline
  MAC catches it.
- **Periodic diff vs continuous monitoring.** A diff says "changed since S1"; SINEC's first-seen
  says *when* (with the caveat that NMS discovery is itself periodic). That is reflection Q3.
- **Definitions card** separates the two axes: change type = *what* differs, classification =
  *why*.

## 5. Trainer–student interaction

| Time | Trainer | Pairs | Type |
|---|---|---|---|
| 0:00–0:08 | Brief: "what changed, and does it matter?" Safety; AI rule (D5). Confirm staging check passed | Pre-flight box (hashes) | Lead |
| 0:08–0:30 | Floor-walk. Watch for: pairs using a different scan than S1 | Start kit capture; start standard scan (background); run collection script; open S2 rack capture | Self-paced |
| 0:30–0:45 | Floor-walk. Watch for: comparing on IP only | T1: `ndiff`, `Compare-Object` on host output, Endpoints ▸ Ethernet vs baseline MACs | Self-paced |
| 0:45–0:50 | **Checkpoint 1:** union of every pair's diff on the whiteboard (no classifying yet). **Hand out the change calendar** | One finding per pair | Whole class |
| 0:50–0:58 | **SINEC demo** on the projector: NMS device list, SSM asset/alert for R1, first-seen times | Watch; note values for R1's case sheet | Demo |
| 0:58–1:25 | Floor-walk. Watch for: K3 closed as "maintenance" without checking the ET 200SP's IP → prompt "who answers ARP for that IP now?" | T2 case sheets | Self-paced |
| 1:25–1:35 | Floor-walk | AI step: paste T1 + case notes; log one correction | Self-paced |
| 1:35–1:42 | **Checkpoint 2:** "K3 and K4 — maintenance or rogue?" Pairs vote and defend with evidence | Share | Whole class |
| 1:42–1:52 | Floor-walk | T3 handover; hash evidence | Self-paced |
| 1:52–2:00 | **Debrief:** reveal the staging log and the detection matrix; reflection Q1–Q3 | Answer | Lead |

Kit reset happens after class, by the trainer, using the reset scripts and an empty-diff proof
(STAGING_LOG §4).

## 6. Student materials

| Item | Status |
|---|---|
| T1–T3 worksheet (maps to W2.1–W2.7) | TODO |
| Definitions card (change type vs classification; owner list) | TODO |
| Change calendar handout | Draft in STAGING_LOG §6 |
| S1 standard scan card and collection script (reused unchanged) | From M2-S1 (M2S1-P4, P5) |
| "Compare with your baseline" cheat sheet: Wireshark filters, `ndiff`, `Compare-Object`, `Get-NetNeighbor` | TODO |

## 7. Alternatives considered

| Alternative | Why not |
|---|---|
| Run the workbook verbatim | Same deviations written 5 times; classification rushed (§1) |
| All plants on the rack, none on the kit | Rack L2 is synthetic for students; nothing to scan or log into. And no hands-on host evidence |
| All plants on the kit, none on the rack | SINEC can't see the kits; W2.5 and reflection Q1 would be empty |
| Fully synthetic SINEC (screenshots only) | Possible fallback if SSM isn't ready, but D2 assumes it will be |
| Plant a single rogue, as the workbook implies | Only one classification is reachable; reflection Q2 ("hidden by a benign one") can't happen |
