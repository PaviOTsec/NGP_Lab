# M1 Session 1 — Classroom plan

The plan for *how the activity actually runs* with 1 trainer, 8 kits and 16 students over
120 minutes. Written minute-by-minute from both the trainer's and the student's seat.

Decisions already locked (from `../LAB_ACTIVITIES_TRACKER.md`): D1–D23.
Session is **familiarisation**, not assessment (D11).

Status tags: `OPEN` · `PROPOSED` · `DECIDED` · `DONE`.

---

## 1. The classroom at a glance

```
                       [ Trainer Rack ]           <-- physical hardware, 1 location
                       |  tour group spot          
                       |  (max 4 teams)            
                       |
   [KIT01] [KIT02] [KIT03] [KIT04]                 <-- 4 kits, Group 1
   [KIT05] [KIT06] [KIT07] [KIT08]                 <-- 4 kits, Group 2
                       |
              [ Trainer floor-walk ]               <-- float between kits
```

- **1 trainer** (D2). No assistant. Nothing in the plan may need two staff.
- **8 kits**, 2 students per kit. Pair roles rotate within the pair.
- Kits named **KIT01–KIT08**, which match the Wi-Fi SSID/VLAN 101–108 (P5).
- **Rack is the only shared physical station.** 8 teams can't crowd it, so the plan uses two
  rotations of 4 teams each.

---

## 2. Materials — what students and the trainer have in hand

### 2.1 Already in hand

| Item | Where | Status |
|---|---|---|
| Workbook (one per student) | `../Module_1_Workbook__Understanding_and_Assessing_OT_Environments.docx` | DONE |
| Rack PCAP | `TR-M1S1-rack-capture.pcapng` (2.4 MB) | DONE |
| Lab Console shared clipboard | MC01, DMZ 10.1.20.56:8766 | Exists, needs Wi-Fi path to kits |

### 2.2 Still to produce (owned by Claude unless noted)

| ID | Item | Why it matters | Status |
|---|---|---|---|
| M1 | Trainer run-sheet (this file, §4) | The script the trainer teaches from | DRAFT below |
| M2 | Student kit walk-through card (A4, 1 side) | Replaces the trainer during self-guided walk-through | PROPOSED (§5) |
| M3 | Wireshark quick-start cheat sheet (A5, 1 side) | For students who've never opened Wireshark | PROPOSED (§6) |
| M4 | Asset-card pack per kit (DMZ↓, ~25 cards) | Primary teaching object for familiarisation (D11, P6) | TODO (operator supplies photos/screens) |
| M10 | **Puzzle pack per kit:** 7 cards + architecture diagram (D24) | The Part A mechanic — see §4a | DRAFT: `puzzle_cards.md` + `puzzle_diagram.{mmd,svg,png}` |
| M5 | Kit Parameter Sheet, **pre-filled per kit** | Saves 5–10 min of class time hunting addresses | PROPOSED |
| M6 | Trainer answer key (W1.1–W1.6 completed) | Marking + debrief; must come after plan is agreed | TODO |
| M7 | Marking rubric (what "complete" means per deliverable) | Sign-off criteria | TODO |
| M8 | Evidence-collection method (how 8 bundles reach the trainer) | Closes the session | OPEN (§7, Q10) |
| M9 | AI access per kit — device, network, prompt crib sheet | AI steps need internet, kits don't have it (§7, Q16) | OPEN |

---

## 3. Pre-class checklist for the trainer

### T-7 days
- Kits powered up for a full cold-run end-to-end: Wireshark opens, Hacker VM boots, PCAP opens.
- Asset-card pack printed and sealed in a KIT0X envelope per kit.
- Parameter sheets pre-filled per kit.
- Wi-Fi + DMZ path from kits to the shared clipboard verified.
- Dry-run the whole 120 minutes with 1–2 colleagues as students.

### T-1 day
- Each kit's workstation: Wireshark 4.6.x present, PCAP already copied to the Desktop as a
  fallback (if the Wi-Fi path fails).
- Nameplates on kits (KIT01 … KIT08).
- Welcome pack per student (workbook, pen, parameter sheet, one evidence USB stick per kit).

### T-30 min
- Boot every kit, open Wireshark, see the empty window; close.
- Trainer logs in to the Lab Console on MC01, uploads today's PCAP to the shared clipboard.
- Red/green status cards on each kit (red = call trainer, green = OK, yellow = question).
- Printed trainer run-sheet open at the rack.
- AI tool open in a browser tab (confirm it responds). Confirm BYOD policy for students.

---

## 4. Trainer minute-by-minute run-sheet (DRAFT)

> **Legend:** `[SAY]` lines are what the trainer actually says. `[DO]` is a trainer action.
> `[STUDENT]` describes what each pair should be doing.

### 0:00 – 0:10  Welcome & brief

- `[DO]` Hand out a welcome pack per student at the door. Point to their KIT nameplate.
- `[SAY]` *"Welcome to Module 1 Session 1 — Understanding the OT environment. You'll meet the
  equipment, see how it talks on the wire, and use an AI chat as a sparring partner, not a
  source of truth. You will leave able to say exactly what every device on this rack does and
  which Purdue level it lives on. Open your workbook to page [X]."*
- Safety rules (3 lines):
  1. **Look, don't touch** the Trainer Rack. If you want a closer look, call me.
  2. **The SIS (Safety Instrumented System) is off-limits** for everything — no scans, no
     clicks, no questions it answers; it only shows what *absence* of its traffic tells you.
  3. **Any alarm, flashing LED, unexpected noise — call me.** Not "finish the row first".
- `[SAY]` *"On evidence: every file you save follows the naming at the top of your workbook.
  Hash each one with `Get-FileHash` before you log it. We'll check in at 1:50."*
- `[SAY]` *"On AI: it is a devil's-advocate. Every claim it makes you'll check against the
  capture. If you can't find the evidence, you don't accept the claim."*
- `[DO]` Hand out: asset-card envelopes to Group 2 kits only (Group 1 goes to the rack first).
- `[SAY]` *"Group 1 — KIT01 to KIT04 — follow me to the rack. Group 2 — KIT05 to KIT08 — your
  kit walk-through card is in your envelope. Start with W1.1 for your kit."*

> **Part A redesign (added 2026-10-14, D24):** the kit walk-through is now an
> **asset-placement puzzle** — see §4a. Groups still swap between the rack tour and the
> kits; what students *do* at the kit changes from "self-guided walk" to "match 7 cards to
> 5 slots using the PCAP, discard 1, mark 1 as undocumented".

### 0:10 – 0:30  Rotation 1 — Group 1 at rack, Group 2 at their kits

**Trainer at the rack with Group 1 (8 students):**

20 min of structured tour. Draw the walk on a whiteboard first — one box per segment.

| Minute | Where / what | Teaching beat |
|---|---|---|
| 0 – 3 | **L0 — 3D model test bed.** Point to each process (CSTR, Transmission/Distribution, Power Generation). | "These are the three real-world things this rack simulates." |
| 3 – 8 | **L1 — physical devices.** CPU 410, ET 200SP, Breaker IEDs, RTU, Wago, L1 switches, OT firewall. | For each: *what it does + the one protocol it speaks*. "CPU 410 runs the pharmaceutical mixing. The I/O rack reads the sensors. They speak PROFINET; the OS server talks to the CPU with S7comm." |
| 8 – 13 | **L2 / L3 (on screens).** OSS01, ES01, L2BM Veeam (name only), Historian. Use the operator console if available. | "The clients you see on operator screens — OSS01 is the SCADA server, ES01 is the engineering station." Point out that OSC terminals aren't in the capture — they sit on a separate switch. |
| 13 – 18 | **DMZ (on screens).** NMS, SIEM, Log Server, DC, ePO, WSUS, SINEMA RC, SINEC INS, SSM. One sentence per asset. | "Think of DMZ as the glass window between IT and OT — these are the inspectors." |
| 18 – 20 | **Loop back to L0.** "This whole stack keeps that physical process safe and running." | Sets up Purdue mapping in Part B. |

**Students at Group 2 kits (no trainer) — the puzzle (§4a):**

- Open the puzzle envelope. Inside: **7 asset cards**, the architecture diagram
  (`puzzle_diagram.svg` printed A3), and the Wireshark cheat sheet.
- Open the PCAP in Wireshark on the kit workstation.
- Match each card to a slot by evidence from the PCAP.
- 20 min target. Fast finishers also start W1.1 rows for their own kit's physical devices.

### 0:30 – 0:50  Rotation 2 — Group 2 at rack, Group 1 at their kits

Same as above with groups swapped.

### 0:50 – 1:00  Puzzle debrief + wider Part A

- `[DO]` Everyone at own kit. Trainer at the front of the room with the diagram projected.
- `[SAY]` *"Hold up the card you discarded."* Pairs lift Card #07 (Allen-Bradley). *"Why?"*
  Expected answers: "no CIP in Protocol Hierarchy", "no Rockwell OUI in Endpoints".
- `[SAY]` *"Hold up the card you marked as undocumented."* Pairs lift Card #06 (Ewon). *"How
  did you know?"* Expected: "second Modbus master on the Wago", "sends to a public IP that
  doesn't answer".
- `[SAY]` *"That — a vendor remote-access router nobody put on the diagram — is the exact
  class of back door we'll trace through real OT incidents in Session 3."*
- `[SAY]` *"The slot gave you the IP; the IP gave you the flows; the flows told you the
  device. That's the OT asset-discovery loop. We'll use it again today."*
- `[DO]` Now the kit workstation PCAP is already open; students move straight into Part B.

### 1:00 – 1:20  Part B — Purdue / Zone mapping + AI challenge

**Students:**
- Fill W1.2 (Purdue level, zone, interfaces, segment, rationale) for every asset in W1.1.
- Pick **two** of their own placements and run them through the AI with the devil's-advocate
  prompt in the workbook.
- Record the AI counter and their defence in W1.3.

**Trainer:**
- Floor-walk. Priority: anyone who hasn't started W1.2 by 1:00, anyone who has an asset at the
  wrong level (common: putting the Historian at L4; it's L3).
- Watch for pairs pasting live credentials or long AI chats verbatim — remind them.

### 1:20 – 1:45  Part C — Communication flow matrix

(The "find the undocumented asset" step moved into the puzzle, so Part C is just the full
flow matrix now.)

**Students:**
1. Open the PCAP in Wireshark.
2. `Statistics ▸ Protocol Hierarchy` — pin on a sticky note the protocols above 1%.
3. `Statistics ▸ Conversations` — sort by packets. Pick the top 10 IP↔IP pairs.
4. Build W1.4 (comm flow matrix): source, dest, protocol, port, direction, frequency, purpose.
5. Find the undocumented asset (W1.5): the hint is "a device at an IP you can't find on any
   asset card, speaking a protocol that doesn't fit its segment".
6. Fill W1.5 using the Card #06 data they already gathered during the puzzle.

**Trainer:**
- Floor-walk. At ~1:25, announce "sort Conversations by packet count — the top three rows
  are the most important flows of the whole process".
- Watch for pairs who open Wireshark and freeze — hand them the quick-start cheat (M3).

### 1:45 – 2:00  Part D — Criticality + AI hallucination + close

**Students:**
1. Prompt the AI (workbook prompt) to rank the rack assets by operational criticality.
2. **One** claim in that ranking will contradict the PCAP. Find it, disprove with a frame #
   or a Conversations row, correct the ranking.
3. Save evidence files (screenshots named `M1-W1-KIT0X-NN-<desc>.png`).
4. Compute SHA-256 for each (one `Get-FileHash` loop; the workbook has the command).
5. Fill the Evidence Log at the end of Session 1. Drop the bundle in the shared evidence
   folder (or hand the trainer the kit USB).

**Trainer:**
- At 1:50 — **go round every kit** with a sticker sheet. One sticker per kit when their
  deliverables (W1.1–W1.6) are *present* (not graded). Formal sign-off happens offline.
- At 1:58 — reflection questions as a 2-min oral debrief. Pick two volunteers:
  - "Which asset was hardest to place on Purdue? What settled it?"
  - "What in the capture told you the SIS is isolated from the BPCS?"
  - "Where did the AI get something wrong? How did you prove it?"

### After class

- Trainer pulls the 8 evidence bundles into one folder, keyed by KIT ID.
- Marks against the rubric (M7).
- Returns signed workbooks + any corrections next session.

---

## 4a. The asset-placement puzzle (D24)

### The pack per kit

| Item | Count | File / where |
|---|---|---|
| Architecture diagram with 5 blank slots | 1 (A3 landscape, laminated or just printed) | `puzzle_diagram.svg` / `.png` (rendered from `puzzle_diagram.mmd`) |
| Asset cards | 7 (A6, 2 A4 sheets, double-cut) | `puzzle_cards.md` |
| Wireshark cheat sheet | 1 (A5) | M3 |
| Dry-erase marker or pencil | 1 | — |

### The puzzle rules (printed on the inside of the envelope)

```
    THE PUZZLE
    You have 7 cards and a diagram with 5 slots.
    5 cards fit the 5 slots.
    1 card belongs to a device nobody added to the diagram.
    1 card doesn't belong on this network at all.

    USE THE PCAP to decide which is which. For every card:
      - Match it to a slot, OR
      - Mark it UNDOCUMENTED (if the device is in the capture but
        not on the diagram), OR
      - Mark it DISCARD (if the device isn't in the capture at all).

    Fill the blanks on each card from Wireshark: IP, MAC, protocols.

    Debrief at 0:50. One trainer, 8 pairs — talk to each other, not
    to me. Lift the red card if you're truly stuck.
```

### Why 7, not 5 or 6

- **5 slots** = covers the key teaching points: one controller, one gateway, one protection
  relay, one PLC with a different protocol, one SCADA server. Students meet every OT
  protocol in play without being overwhelmed by all 30+ assets.
- **1 undocumented card** (Ewon Cosy) = the "undocumented asset" moment is now embedded in
  the puzzle rather than tacked on in Part C. Students discover it, nobody tells them.
- **1 discard card** (Allen-Bradley ControlLogix) = teaches that *"this device is not in the
  capture"* is a valid analytical result. Students have to prove *absence*, which forces
  them into Protocol Hierarchy and Endpoints rather than just filtering by known IPs.

### What makes a pair "done" on the puzzle

- All 7 cards sorted into A/B/C/D/E/Undocumented/Discard.
- IP, MAC and protocol list filled for the 6 cards that *are* on the network.
- One sentence per card on *"how I knew"* — the trainer sampling at the debrief picks a
  card at random and asks the pair to say what evidence placed it.

### Common wrong turns + trainer prompts

| Wrong turn | Prompt |
|---|---|
| Pair tries to place Card #07 (AB) because "it's a PLC and we have a slot" | *"Filter `enip` or `cip` in Wireshark. What do you see?"* |
| Pair misses Card #06 (Ewon) because they placed it in Slot D (WAGO's slot) | *"Slot D's IP is 192.168.4.13. The card's device matches 192.168.4.50. Different IP — is it the same device?"* |
| Pair places OSS01 (Card #05) in Slot A (CSTR controller) | *"OSS01 is a Windows server. Does Slot A's IP (192.168.1.10) look like a Windows VM MAC or a Siemens PLC MAC?"* |
| Pair just reads off IPs from Slots without checking Wireshark | *"Walk me through one flow in the Conversations list that involves Slot C's IP."* |

---

## 5. The self-guided kit walk-through card (M2) — sketch

A single sided A4 that stands up on the kit. Suggested layout:

```
+----------------------------------------------------+
| Your kit — a mini pharma CSTR                      |
| 20 minutes. Don't open the panel.                  |
|                                                    |
| 1. Find the devices in order:                      |
|    ( ) Workstation (VM)         ( ) XC208G switch  |
|    ( ) SC646 firewall           ( ) CPU 410        |
|    ( ) ET 200SP I/O                                |
|                                                    |
| 2. For each, record in W1.1 (your kit rows only):  |
|    - Model (on the label)                          |
|    - IP (from the parameter sheet)                 |
|    - MAC (switch WBM; see sticky note on monitor)  |
|    - Role (what it does — one sentence)            |
|                                                    |
| 3. Done early? Start W1.2 Purdue mapping for the   |
|    kit devices only. Trainer joins us at 0:50.     |
|                                                    |
| Stuck? Raise the yellow card.                      |
+----------------------------------------------------+
```

Keeps students on task without a trainer. The actual card gets concrete field values once
Q6/Q11 are answered.

---

## 6. Wireshark quick-start cheat sheet (M3) — sketch

```
    OPEN THE PCAP
    File > Open > TR-M1S1-rack-capture.pcapng

    SEE WHO IS ON THE NETWORK
    Statistics > Endpoints > IPv4

    SEE WHAT THEY'RE TALKING ABOUT
    Statistics > Protocol Hierarchy

    SEE EACH CONVERSATION
    Statistics > Conversations > TCP   (sort by Packets, descending)

    FILTER BY ADDRESS
    ip.addr == 192.168.4.13           (in Display Filter)

    FILTER BY PROTOCOL
    modbus       s7comm       mms      goose       lldp

    FILTER BY FUNCTION
    modbus.func_code == 6             (write single register)
    modbus.func_code == 16            (write multiple registers)

    FIND A SUSPICIOUS DEVICE
    Statistics > Endpoints   -> sort by Packets, look for IPs that
    aren't on your asset cards. Hover for OUI (vendor) hints.

    SAVE EVIDENCE
    File > Export Specified Packets   (filtered)   OR
    screenshot the whole window with Snipping Tool
```

---

## 7. Failure modes & what the trainer does

| Fails | Visible as | Trainer action |
|---|---|---|
| Wi-Fi path to kits down | Kit can't fetch the PCAP | Fall back to the kit's Desktop copy; USB-stick-of-last-resort |
| Wireshark won't open on a kit | Kit stuck at pre-flight | Give the pair the trainer's laptop screen for Part C only; mark the kit for post-class fix |
| A kit VM is in a bad state | Kit can't do W1.1 | Pair that team with a neighbour; two pairs on one kit for Parts A/B is fine for S1 |
| AI tool rate-limits or dies | AI column in W1.3/W1.6 blank | Allow completion with trainer-as-devil's-advocate; mark the AI column as "deferred" |
| Pair finishes 30 min early | Hangs around | Challenge: "Find another protocol in the capture that isn't on your W1.4. Add it." |
| Pair is 30 min behind | Blank workbook at 1:40 | Trainer intervenes: fill W1.1 together, hand them pre-written W1.2 as a starter, make sure Part C is at least opened |
| A student starts "nmaping" the kit | Discovery tool usage before Q9 is answered | Stop immediately. S1 is passive. Scans wait for S2. |

---

## 8. What the student sees — a time-lapse of KIT03

- **0:00**  Walks in, finds KIT03 nameplate, sits down with partner. Workbook, pen, parameter
  sheet, USB stick, two cans of water on the table.
- **0:05**  Reads the first page while trainer talks.
- **0:10**  "Group 2" — opens the asset-card envelope. Finds a card for every device on the
  kit, plus a stack of rack cards they'll use later.
- **0:12**  Starts the walk-through. Peers at the little labels. One of the pair reads out,
  the other writes.
- **0:28**  Finished W1.1 for the kit. Starts W1.2 for the kit devices.
- **0:30**  Trainer calls "swap". Walks to the rack. Hears the rack tour.
- **0:50**  Back at the kit. PCAP is already on the Desktop. Opens it in Wireshark.
- **0:55**  Trainer: "there's an undocumented device". Pair notes it in margin, starts B.
- **1:10**  AI challenge: they ask the chat to argue that OSS01 is Level 2 rather than L2
  System Network's "Level 2 Purdue". AI says yes. They push back with the Conversations tab
  showing OSS01 ↔ CPU410 S7comm. They record "kept".
- **1:25**  Protocol Hierarchy — point and read. Pin a sticky with: PNIO, GOOSE, Modbus,
  S7comm, MMS, SNMP, NTP, DNS.
- **1:35**  Endpoints — see 192.168.4.50 with HMS Industrial Networks OUI. Not on any card.
  Filter `ip.addr==192.168.4.50`. See Modbus to the Wago plus SYNs to 203.0.113.80.
  Fill W1.5 with "likely a vendor remote-access gateway, back door around the DMZ".
- **1:45**  AI ranks assets. Says the Historian is the most critical. They search `ip.addr`
  for the historian in the PCAP. OPC UA to OSS01 only. No control flow. Correct AI's rank;
  log the hallucination.
- **1:55**  Screenshots named, hashed, saved. Evidence log filled. Trainer puts a sticker on
  the W1.6 corner. Pair high-fives.

If any of those beats breaks, the plan isn't working.

---

## 9. Still-open logistical questions

| # | Question | Why it blocks | Default proposal |
|---|---|---|---|
| L1 | **AI access per kit:** BYOD phone, kit workstation (with internet enabled for that step), or shared tablet? | Part B and Part D need it | BYOD phone — simplest. Workbook has a QR to the agreed AI URL. |
| L2 | **Evidence collection:** shared folder on MC01, Lab Console shared clipboard upload, or USB stick returned to trainer? | Session end | USB stick returned to trainer. Reliable, no network dependency. |
| L3 | **Kit baseline reset between cohorts:** who re-copies the PCAP, resets screenshots folder, etc. (no VM checkpoints, D20)? | Next cohort | Short reset playbook: delete `Desktop\M1-S1`, re-copy PCAP, confirm Wireshark opens |
| L4 | **Walk-through card content:** real kit IPs and MACs from the operator or trainer, since Claude can't read L1/L2 (rule 13) | M2 | Operator fills in once; stays stable per cohort |
| L5 | **Who prints the asset-card pack?** | T-7 days | Operator or academic admin |
| L6 | **Where in the room do the two groups do the walk-through?** Rack is one spot — are the kits in the same room? | Pre-class layout | Assume same room, L-shaped layout |

---

## 10. Open questions summary (for the operator)

1. OK with the two-rotation plan (§4), or prefer all 8 teams through the rack back-to-back?
2. AI access: BYOD phones, or something else?
3. Evidence collection method?
4. Can you supply kit IP/MAC values for M2, or should they also come from student discovery?
5. Which Part D hallucination do you want to be the "guaranteed catch" one — Historian?
   OS-clients-talk-to-CPU? Something else?
6. Should the trainer or Claude write M4 (asset-card pack)? Claude can draft text; operator
   supplies photos and screenshots.

---

## 11. Status

| Item | Owner | Status |
|---|---|---|
| This plan (M1) | Claude + operator | DRAFT v2 (puzzle twist added) |
| Walk-through card M2 | Claude drafts; operator fills kit values | TODO |
| Wireshark cheat sheet M3 | Claude | TODO |
| Asset-card pack M4 (full ~25 for Parts B–D reference) | Claude drafts text; operator supplies images | TODO |
| Parameter sheet M5, pre-filled | Operator | TODO |
| Answer key M6 | Claude | DRAFT (ANSWER_BOOK.md) |
| Marking rubric M7 | Claude | TODO (after plan is agreed) |
| Evidence collection M8 | Operator decision | OPEN |
| AI access per kit M9 | Operator decision | OPEN |
| **Puzzle pack M10** | Claude drafts; operator picks photos | DRAFT (`puzzle_cards.md` + `puzzle_diagram.svg`) |
