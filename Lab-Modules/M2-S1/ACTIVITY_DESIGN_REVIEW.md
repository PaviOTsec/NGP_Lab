# M2-S1 — Activity Design Review

Before planning the logistics: is Session 1 worth running as written? What does it really teach?
Is that the best way to teach it, and how do the trainer and students actually interact?
Decisions that come out of this review are logged in `M2_S1_TRACKER.md` (§11).

Status: **PROPOSED**. Awaiting operator review (M2S1-Q15 to Q18).

---

## 1. Verdict

**The activity is worth running. It teaches a real, transferable skill. As written, though, it
is too wide for 120 minutes, and much of it repeats M1-S1.** It needs a sharper central question
and some support material, not a different activity.

- **What it gets right.** It follows the order real OT asset discovery uses: passive first, then
  narrow active probing, then host evidence, then judgement. It also asks students to say *how
  sure* they are about each entry. That is the habit that separates an inventory you can defend
  from a list.
- **What goes wrong if it runs verbatim:**
  - 7 tables, 3 tools, 3 AI steps and web research in 120 minutes.
  - Pairs will spend the session filling rows: copying Endpoints into W1.1, nmap output into
    W1.2, PowerShell output into W1.3.
  - The two parts that hold the learning, the **confidence judgement (W1.6)** and the **lifecycle
    judgement (W1.5)**, come last and get rushed.
  - Part A also repeats M1-S1 Part C almost exactly (same rack, same Wireshark views).
- **The fix:** keep the workbook's tables, but reframe the session around one question:
  **"What do we know, how do we know it, and how sure are we?"**

  Three changes carry most of the improvement:
  1. Part A becomes **reconciliation**: the diagram against the wire (M2S1-D3).
  2. Active and host work run on **"the cell you are allowed to touch"**: the kit (M2S1-D1).
  3. A **confidence rubric** and a **narrowed lifecycle set**, so the judgement parts get time.

## 2. What the session is really teaching

Stripped down, Session 1 teaches four ideas:

1. **Every source sees only part of the network.**
   - Passive capture sees only devices that talk during the window.
   - Active scanning sees only devices and ports that answer, and it injects traffic into a
     control network.
   - Host evidence sees only machines you can log into.
   - Documentation sees whatever someone remembered to write down.
2. **Confidence comes from independent sources agreeing.** It does not come from how sure an
   entry sounds.
3. **An inventory is only useful once it is tied to support status.** An asset past end-of-support
   carries different risk and needs a different plan than one that can still be patched.
4. **AI speeds up drafting but invents specifics.** Advisory IDs, dates and device roles are
   exactly what it makes up.

Session 2 depends on this. It diffs a new scan against this baseline using **New / Missing /
Modified / Undocumented**. If Session 1 teaches the categories *documented-and-seen,
documented-but-silent and seen-but-undocumented*, Session 2 is the same idea applied over time.
That coherence is the strongest argument for the reconciliation framing below.

## 3. Problems with the workbook as written

| # | Problem | Effect on learning | Fix (section) |
|---|---|---|---|
| 1 | Part A repeats M1-S1 Part C: same rack, same Endpoints/Conversations views | Little new learning; students already found the rack's devices in M1 | Reframe as **reconciliation against the diagram** (§4, Part A) |
| 2 | Passive evidence is from the rack, but active and host evidence are from the kit | "Merge one profile per device" and reflection Q2 have nothing to merge | M2S1-D1: the kit gets all three sources; rack gets passive + M1 (§4) |
| 3 | Commands are given verbatim with no explanation of flags or output | Students copy without understanding why `-T2`, `-Pn` or `--scan-delay` are there, which defeats "OT-safe" | **Appendix B** + a live scan-footprint demo (§5) |
| 4 | "Confidence H/M/L" and "Observed/Inferred/Assumed" are never defined | Every pair invents its own scale, so the trainer can't mark it and pairs can't compare | **Appendix E**: one rubric linking both (§6) |
| 5 | Lifecycle research on up to 10 assets, no starting sources | 25 minutes of searching; weak pairs give up; AI answers get copied | 4–5 chosen assets, a sources card and one modelled lookup (§4, Part D) |
| 6 | The PowerShell block includes `Win32_Product` (triggers MSI repair checks) and ~10 hand-typed commands | Typing time, plus a real risk to a PCS 7 workstation | A read-only collection script; registry in place of `Win32_Product` (Appendix C) |
| 7 | Three AI steps, each needing a large paste | Time cost; the middle one (correlate P/A/H) overlaps with W1.4 | Keep two: (a) passive asset list, (b) lifecycle. Use AI to *draft* W1.4, then verify (§4) |
| 8 | One trainer, seven tables, no built-in pauses | The trainer becomes a passive floor-walker; nobody pulls the class together | Three short demos + two whole-class checkpoints + one approval gate (§5) |
| 9 | The baseline lands in Word tables | Session 2 must diff it; diffing Word tables by eye is slow and error-prone | Give W1.4 as a **CSV/XLSX template** too, so S2 can diff it (§6) |

## 4. Recommended shape, part by part

The workbook tables, numbering and deliverables stay unchanged. What changes is the *question
each part asks*, and what the trainer adds.

### Part A — "Does the diagram match the wire?" (W1.1)

- **Input:**
  - the **architecture diagram**, issued as "the documentation we inherited";
  - the rack PCAP (M2S1-D2);
  - the pair's M1 inventory.
- **Task:** fill W1.1 as before, but sort every device into one of three buckets:

  | Bucket | Meaning | What it teaches |
  |---|---|---|
  | **Documented & seen** | On the diagram and in the capture | Corroborated by two sources |
  | **Documented, not seen** | On the diagram, silent in the 15-min window | Passive capture's blind spot; this *motivates* Part B |
  | **Seen, not documented** | In the capture, missing from or misplaced on the diagram | The planted device (M2S1-D3) |

- **The planted device (M2S1-D3):**
  - It talks only a few times in the capture, so it is easy to miss in Endpoints.
  - Its role has to be **inferred from behaviour** (who it talks to, when, using what), not read
    off a label.
  - This is what makes Part A different from M1: M1 asked *"what is this?"*, M2 asks *"how do you
    know, and what is missing?"*
- **AI step (kept):** paste the Endpoints/Protocol Hierarchy summary and ask for an asset list.
  The AI usually labels every Windows host "HMI", or invents devices that aren't in the data.
  That gives W1.7 its first entries.

### Part B — "The cell you're allowed to touch" (W1.2)

- **Framing:** on a real plant you can usually only *watch* production, the way we treat the rack.
  Active scanning happens on a cell in a maintenance window with approval, the way we treat the
  kit. Saying this out loud teaches *where* active discovery belongs.
- **Trainer demo (before anyone scans):**
  - The trainer runs the approved scan against **one kit** on the projector, with Wireshark open
    on the same link.
  - The class sees the packets the scan puts onto the control network and how many reach the
    PLC.
  - "OT-safe" becomes something visible, not a slogan.
- **Approval gate:** each pair shows the trainer its target list and timing profile on a one-line
  scan card. The trainer initials it, and only then do they scan. This is the workbook's "trainer
  has confirmed scope", done as a real control.
- **What students look for:**
  - Devices from the "documented, not seen" bucket that answer a scan.
  - Ports that passive capture never showed (WBM on 80/443, SMB on 445).
  - Things a TCP scan cannot show (SNMP, PROFINET discovery on UDP). Appendix B explains why.

### Part C — Host evidence (W1.3)

- A **read-only collection script** (Appendix C) runs the workbook's command set, with
  `Win32_Product` replaced by a registry read. It writes named files and hashes them, so the
  time goes to *reading* the output, not typing it.
- **What students look for** (Appendix C lists these):
  - age of the last patch;
  - unexpected running services or autoruns;
  - local admin accounts;
  - USB history (it feeds Session 3).
- **AI correlation step:** folded into Part D. AI drafts the merged W1.4 rows; students verify
  each field against a named source.

### Part D — Judgement (W1.4, W1.5, W1.6, W1.7)

- **W1.4 Unified Inventory.**
  - Kit rows: P + A + H + M1.
  - Rack rows: P + M1.
  - Confidence follows the **rubric** (Appendix E). The difference between kit and rack rows
    *is* the lesson: same pair, same afternoon, very different confidence.
- **W1.5 Lifecycle.**
  - **4–5 assets**, chosen so the verdicts differ: one supported, one in extended support, one
    with a vendor advisory to read, one where the firmware is behind the latest release.
  - **Sources card** (Appendix D) with starting URLs.
  - The trainer **models one lookup live** first: product, then the vendor lifecycle page, then
    ProductCERT.
  - Pairs then do the rest, AI first and then the vendor page, as the workbook says.
- **W1.6 Confidence report.** Students write it from the W1.4 confidence column. The prompt is:
  *"For each Low, name the one collection step that would raise it."* That is also reflection
  Q1.
- **W1.7 AI log.** Entries come in naturally from Part A (role labels) and W1.5 (dates and
  advisory IDs). Two errors is easy to reach.

## 5. Trainer–student interaction

One trainer, eight pairs. The trainer leads at **three short demos**, controls **one gate**, and
pulls the room together at **two checkpoints**. The rest of the time pairs work alone and the
trainer floor-walks with specific things to watch for.

| Time | Trainer | Pairs | Interaction type |
|---|---|---|---|
| 0:00–0:10 | Brief. The question of the day: *"what do we know, how do we know it, how sure are we?"* Hand out the diagram as "inherited documentation". Safety and AI rules (incl. D5 vs workbook wording) | Pre-flight; start a 5-min passive capture on the kit (runs during the brief) | Lead |
| 0:10–0:15 | **Demo 1**: where the rack capture was taken (SPAN points on the diagram), and what that vantage *cannot* see | Watch | Demo |
| 0:15–0:40 | Floor-walk. Watch for: pairs listing IPs without bucketing them; nobody opening Endpoints ▸ Ethernet (OUIs) | Part A: reconcile diagram vs PCAP → W1.1; AI asset list | Self-paced |
| 0:40–0:45 | **Checkpoint 1**: "What's on the diagram but silent? Why might it be silent?" Collect answers on the whiteboard. *Don't* reveal the planted device | Share one finding per pair | Whole class |
| 0:45–0:55 | **Demo 2**: approved scan of one kit with Wireshark on the projector (scan footprint). Then the **gate**: initial each pair's scan card | Watch; fill in the scan card; get it initialled | Demo + gate |
| 0:55–1:15 | Floor-walk. Watch for: anyone scanning outside the card; pairs waiting on the scan instead of starting Part C | Part B scans in the background; Part C script → W1.3; W1.2 when the scan finishes | Self-paced |
| 1:15–1:22 | **Checkpoint 2**: "What did the scan find that the capture missed, and the reverse?" (reflection Q2). Then **Demo 3**: one lifecycle lookup modelled live | Share; watch | Whole class + demo |
| 1:22–1:47 | Floor-walk. Watch for: AI dates copied without a vendor URL; confidence "H" on rows with one source | Part D: W1.4 (AI draft → verify), W1.5, W1.6 | Self-paced |
| 1:47–1:53 | Floor-walk; presence check of deliverables | W1.7; hash evidence | Self-paced |
| 1:53–2:00 | **Debrief**: reveal the planted device and the behaviour that gave it away; reflection Q1 and Q3; one sentence on how this baseline is used in Session 2 | Answer | Lead |

Why this shape works for one trainer:
- Every demo is something the trainer would otherwise explain eight times.
- The gate is the one moment the safety rule needs a human.
- The checkpoints stop the room splitting into "finished" and "lost", and give weaker pairs the
  answers they need to continue without the trainer sitting with them.

## 6. Student support: appendices

The workbook assumes students already know Nmap, PowerShell, discovery protocols and vendor
lifecycle terms. M1 used Wireshark only. Short appendices close the gap. Each one *explains*: what
the tool or command shows, why it is set that way, and what a normal result looks like in this
lab.

| Appendix | Content | Length | Used in |
|---|---|---|---|
| **A — Wireshark for discovery** | What each discovery filter in the workbook reveals (ARP, DHCP opt 12/60, NBNS/LLMNR/mDNS, LLDP/CDP, browser, S7/COTP, Modbus/DNP3/104). Which ones are **expected to be empty here, and why** (static IPs → no DHCP; no Computer Browser on Server 2019+). Reading OUIs; exporting Endpoints to CSV | 2 pages | Part A |
| **B — Nmap in OT** | Each flag in the two workbook commands and *why it is there*. open / closed / filtered. Why TCP `-sT` can't see SNMP or PROFINET (UDP). The "avoid" list explained (`-O`, `-A`, NSE). Reading `.nmap` / `.gnmap` / `.xml`. Using the same method in S1 and S2 so the diff is honest | 2 pages | Part B |
| **C — PowerShell host evidence** | The collection script; each section of its output; "what to look for" (patch age, odd services, autoruns, admin accounts, USB history); why `Win32_Product` is not used | 2 pages | Part C |
| **D — Lifecycle and vendor sources** | Supported / extended / EoS / EoL in plain words. Where to look: Siemens product lifecycle and SIOS, ProductCERT advisories (how to read affected versions + remediation), Microsoft Lifecycle, other vendors' EoL pages. How to cite a source | 1–2 pages | Part D |
| **E — Confidence rubric** | Observed / Inferred / Assumed with lab examples, and how they map to H/M/L. Proposed: **H** = observed by ≥ 2 independent sources that agree; **M** = observed by 1 source, or 2 that partly conflict; **L** = inferred or documented only. "What would raise it" examples | 1 page | Parts A–D |
| **F — Checking the AI** | The signs of a made-up answer (precise IDs/dates with no link, confident roles from an IP alone). How to fill a W1.7 row. Two worked examples | 1 page | Parts A, D |

Plus two handouts:
- **Scan card**: the target list, timing profile, initials box and stop conditions.
- **W1.4 CSV/XLSX template**: the same columns as the workbook table, so Session 2 can diff it.

## 7. Alternatives considered

| Alternative | Why not (or not now) |
|---|---|
| Run the workbook verbatim | Breadth beats depth; repeats M1; the judgement parts get rushed (§3) |
| Reuse the M1-S1 PCAP unchanged | No hostnames or firmware on the wire; it has the DNS bug; M2S1-D2 assumes an enriched capture instead |
| Kit only (drop the rack PCAP) | Loses the "diagram vs wire" reconciliation and the planted device, which are the best parts. The kit is too small for a meaningful passive inventory |
| Rack only (no kit scanning) | Active scanning of shared rack L1 devices by 8 pairs breaks the workbook's own safety rules and CLAUDE.md rule 13 |
| Add SINEC Security Monitor's automatic asset inventory as a 4th source ("tool vs manual") | Good lesson, but the workbook brings SSM/NMS in Session 2, and SSM sees the *live* rack, not the synthetic capture. Better kept for S2 |
| Give a pre-researched lifecycle pack instead of live research | Saves time, but removes the "validate against the vendor page" skill the workbook names. Keep it only as the trainer's fallback if internet or BYOD fails |

## 8. Decisions needed

See the tracker (M2S1-Q15 to Q18):
1. Adopt the reconciliation framing for Part A, with three buckets?
2. Adopt the interaction shape (3 demos, 1 gate, 2 checkpoints)?
3. Appendices A–F, the scan card and the W1.4 template: all of them, or a subset?
4. Lifecycle set of 4–5 deliberately different assets instead of "all assets"?
