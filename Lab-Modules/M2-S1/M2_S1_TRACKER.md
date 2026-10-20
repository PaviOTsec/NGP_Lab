# M2 Session 1 — Passive Asset Discovery, Inventory Baseline and Asset Lifecycle Review · Preparation Tracker

Tracks how workbook **Module 2, Session 1** will be run in this lab: discussion, decisions,
open questions and preparation progress, covering the whole delivery (trainer, students,
logistics, synthetic materials, answer book). Everything for this activity lives in
`Lab-Modules/M2-S1/`.

IDs are prefixed `M2S1-` so they never clash with M1-S1 (`D1`–`D23`) or M1-S2 (`S2-`).
All-session decisions from M1-S1 apply here: **D2** (16 students, 1 trainer, 8 kits),
**D5** (web AI chat on BYOD, lab IPs may be pasted), **D12** (the lab as it really is wins over
the drawing), **D20** (no SIS traffic in any synthetic capture).

**Status tags:** `OPEN` · `PROPOSED` · `DECIDED` · `TODO` / `IN PROGRESS` / `DONE`

---

## 1. Status at a glance

| Phase | Status | Next step |
|---|---|---|
| Workbook read and mapped to the lab | DONE (2026-10-14) | — |
| Tracker draft (§1–§8) | DONE (2026-10-14) | — |
| **Activity design review** (does it teach well? interaction? student guides?) | PROPOSED: `ACTIVITY_DESIGN_REVIEW.md` | Operator answers M2S1-Q15 to Q19 |
| Evidence scope: which devices get P / A / H evidence | DECIDED (M2S1-D1) | — |
| Rack passive capture | DECIDED (M2S1-D2): assumed to exist with a discovery layer; not built now | — |
| Planted device | DECIDED (M2S1-D3): a rarely-talking device altered on the diagram | Pick the device (M2S1-Q19) |
| Kit facts (IPs, VLANs, scan host, EWS account) | DEFERRED (operator: activity design first) | Revisit when the classroom plan is written |
| Classroom plan | TODO | After the design review is agreed |
| Synthetic materials (PCAP) | DEFERRED (M2S1-D2) | — |
| Answer book | TODO | After the PCAP + kit facts |
| Student materials (cards, cheat sheets) | TODO | After the classroom plan |
| Dry run | — | — |

## 2. Sources

- **Workbook:** `Lab-Modules/Module_2_Workbook__OT_Asset_and_Configuration_Management.docx`,
  Session 1 (tables W1.1–W1.7, Kit Parameter Sheet, safety rules, evidence naming `M2-W1-…`).
- **Architecture drawing:** `Architecture/OT_Cybersecurity_Lab_Architecture_v0.3 (1).pdf`. Use it
  only where reality is unknown (D12).
- **Observed inventory:** `config/inventory.yaml` (DMZ, L3, L4, L5; L2 and below excluded by design).
- **Saved real outputs (L1/L2 MACs, routing):**
  `%LOCALAPPDATA%\LabConsole\nms-onboarding\20261012-topology\`, `Backups/20261013-wap-readonly/`.
- **M1-S1 template + rack facts:** `Lab-Modules/M1-S1/` (tracker §1.2/§1.2a/§1.4, answer book
  W1.1 rack rows, PCAP `TR-M1S1-rack-capture.pcapng`, spec `tools/lab-pcap/spec/m1s1.yaml`).
- **M1-S2 kit reality:** `Lab-Modules/M1-S2/M1_S2_TRACKER.md` §0: kit host is Windows +
  VirtualBox running the EWS VM and a Kali VM (S2-D4); live OT traffic on the kit (S2-D5); kit
  devices deliberately unreachable from MC01 for now (S2-D6).
- **NMS / SNMP reality:** `docs/NMS_ONBOARDING.md`. The real network devices use SNMPv3
  authPriv only.
- **Memories:** lab-activities-planning, no-vm-checkpoints-licensing,
  phase-reports-and-visible-browser, trainee-wifi-ap-project, nms-onboarding-project.

## 3. Standing constraints

- **CLAUDE.md rule 13.** Claude and the Lab Console never touch L2 or below on the rack. Building
  a synthetic PCAP offline on MC01 touches no device. Kit devices: Claude *may* work on them
  (S2-D6), but they are unreachable today, so kit facts come from the operator.
- **Rule 14, observe-only.** Anything Claude collects from the live DMZ/L3 (e.g. M2S1-P10) is
  read-only and needs the operator's go-ahead first.
- **No Hyper-V checkpoints of lab VMs** (they void the licences). Kit reset relies on files and
  the kit's own reset, not on checkpoints.
- **Class shape (D2):** 1 trainer, ~16 students, 2 per kit, 8 kits (KIT01–KIT08 = Wi-Fi
  SSID/VLAN 101–108). Nothing may need a second staff member.
- **SIS silent (D20):** no 192.168.2.* traffic in any synthetic capture. `<TR_SIS_SEG>` is never a
  scan target.
- **Pedagogical focus:** M2 is *not* first contact. Students have done M1 and already know the
  rack. The workbook says this session builds a **defensible baseline** and asks for
  **confidence** on every entry. So the focus is **evidence quality and confidence**, with
  familiarisation only as needed. *(D11 was M1-S1 only; confirm the M2 focus, M2S1-Q14.)*
- **Workbook safety rules for this module:** OT-safe scanning only, on trainer-approved targets,
  with conservative timing. Stop on any alarm. No `-O`, `-A`, `-sV` above intensity 2, UDP sweeps
  or NSE. AI is a challenger. Every CVE, lifecycle date or advisory is verified on the vendor page.

## 4. What the workbook asks for

**Duration:** 120 min. **Unit:** a pair per Trainee Kit. **Scenario:** incomplete visibility.
Build a defensible asset + lifecycle baseline from passive, active, host and vendor evidence,
and state your confidence in each entry. **This baseline is the reference point for Session 2**
(rogue-asset detection and diff), so whatever S1 produces, S2 must be able to re-run and compare.

| Part | What happens | Tool | Output |
|---|---|---|---|
| Pre-flight | M1 inventory to hand; Kit Parameter Sheet incl. `<APPROVED_TARGETS>`/`<SCAN_HOST>`; PCAP opens; Nmap can reach the targets and **not** the SIS; PowerShell rights; trainer confirms scan scope and timing; AI access; evidence folder | — | Ticked checklist |
| A — Passive discovery | Trainer shows the passive capture points on the rack, then hands out `<TR_PCAP_NAME>`. Endpoints / Conversations / Protocol Hierarchy, plus discovery filters (arp, dhcp, mdns/llmnr/nbns, cdp/lldp, browser, s7comm/cotp, modbus/dnp3/iec104). AI extracts an asset list from a pasted summary; compare | Wireshark, AI | **W1.1** Passive Discovery Findings |
| B — Active discovery | `nmap -sn --disable-arp-ping`, then `-sT -Pn -T2 --scan-delay 200ms` on 14 TCP ports against `<APPROVED_TARGETS>` only; save `-oA` | Nmap | **W1.2** Nmap Discovery Findings |
| C — Host evidence | PowerShell on the Windows workstation: identity/OS, IP, hotfixes, installed software (`Win32_Product`), running services, autoruns, local users, USBSTOR history. AI correlates P/A/H into one profile per asset | PowerShell, AI | **W1.3** Windows Host Evidence |
| D — Inventory, lifecycle, confidence | Merge P/A/H + M1 into one inventory. Research support status, firmware lifecycle, EoS/EoL, advisories (AI first, then the vendor page). AI classifies legacy constraints | AI, vendor pages | **W1.4** Unified Inventory (12 rows), **W1.5** Lifecycle Register, **W1.6** Confidence Report, **W1.7** AI Validation Log (≥ 2 AI errors) |
| Close | Evidence named `M2-W1-<KIT_ID>-<step>-<desc>.<ext>`, SHA-256 logged; 3 reflection questions; sign-off | PowerShell | Evidence Log |

**Reflection questions:** (1) the weakest-evidence asset and the one collection step that would
fix it; (2) what active found that passive missed, or the reverse, and why; (3) where the AI's
lifecycle info disagreed with the vendor page and how it was resolved.

## 5. Terms-to-lab mapping

### 5.1 Kit Parameter Sheet placeholders

Rack/central values come from `config/inventory.yaml`. Kit values come from the drawing and are
**unconfirmed** until the operator checks one kit (M2S1-Q4).

| Placeholder | Proposed value | Source / status |
|---|---|---|
| `<KIT_ID>` | KIT01–KIT08 | M1-S1 P5 |
| `<PLC_IP>` | 192.168.10.10 (CPU 410, VLAN A) | Drawing; unconfirmed |
| `<ET200SP_IP>` | 192.168.10.11 | Drawing; unconfirmed |
| `<HMI_WS_IP>` / `<ENG_STATION_IP>` | 192.168.110.10, the **same** VM ("Operator + Engineering Station") | Drawing; the workbook lists two hosts, the kit has one (M2S1-G15) |
| `<SC646_MGMT_IP>` | ? | Unknown (M1 Q6 still open) |
| `<XC208_MGMT_IP>` | 192.168.110.30 | Drawing; unconfirmed |
| `<KIT_SUBNET>` | **Two** subnets: 192.168.10.0/24 (control, VLAN A) + 192.168.110.0/24 (system, VLAN B) | Drawing; the workbook assumes one |
| `<KIT_GW>` | SC646 (address ?) | Unknown |
| `<OT_VLAN>` / `<SUPPORT_VLAN>` | VLAN A / VLAN B IDs ? | Unknown |
| `<SCAN_HOST>` | Kali VM on the kit host (bridged on the EWS cable, S2-D7), or the EWS VM | M2S1-Q5 |
| `<APPROVED_TARGETS>` | An **explicit host list** of the kit devices (M2S1-P4), not the whole subnet | Proposal |
| `<TR_PCAP_NAME>` | `TR-M2S1-rack-passive.pcapng` (if M2S1-P2 is accepted), else `TR-M1S1-rack-capture.pcapng` | M2S1-Q2 |
| `<TR_SIS_SEG>` | 192.168.2.0/24 (rack SIS island) | M1-S1 §1.2 |
| `<SINEC_NMS_URL>` | https://192.168.30.11 (on MaintServer) | Inventory; needed in S2, not S1 |
| `<SINEC_SSM_URL>` | https://10.1.20.18:8443 | Inventory; S2 |
| `<SPLUNK_URL>` | http://10.1.20.15:8000 (http/https unconfirmed) | Inventory; S3 |
| `<WSUS_SERVER>` | WSUS (10.1.20.12), port 8530 | Inventory; S4 |
| `<AD_DOMAIN>` | np.local (OT-host OU ?) | Inventory; S4 |
| `<BACKUP_STORE>`, `<FW_IMAGE_GOOD/TEST>` | — | S3/S4, not this session |
| `<AI_TOOL>` | Web AI chat on BYOD | D5 |
| `<EVIDENCE_STORE>` | ? (M1 Q10 / L2 still open; M1 default: USB stick per kit) | Open |

### 5.2 Workbook terms

| Workbook says | In this lab |
|---|---|
| "Shared passive PCAP" / "passive capture locations on the Trainer Rack" | Synthetic multi-point SPAN capture of the rack, DMZ and below, no VLAN tags (M1-S1 D4, D7, D14, D18) |
| "The Windows workstation" | The kit's **EWS VM** (Operator + Engineering Station) on the kit host |
| "Any other approved Windows host" | Not defined. Candidates: the kit host itself, or rack DMZ/L3 Windows VMs through a pre-collected evidence pack (M2S1-P10) |
| `<SCAN_HOST>` "workstation or Kali" | Kali VM or EWS VM on the kit host (S2-D4) |
| "Module 1 Asset Inventory" | The pair's own M1-S1 W1.1/W1.2 (+ the M1 answer book as fallback) |
| "Central infrastructure" | DMZ services: Splunk 10.1.20.15, SINEC NMS 192.168.30.11, SSM 10.1.20.18, WSUS 10.1.20.12, DC 10.1.20.17. Not used in S1 |
| "RTU", "relay" (never scan) | Rack SICAM A8000 (192.168.3.12) and SIPROTEC 5 IEDs (192.168.3.10/.11). On the rack only, never in kit scope |
| "Vendor page" | Siemens ProductCERT / SIOS support portal, Microsoft Lifecycle, Palo Alto / Fortinet EoL pages |

## 6. Observations and gaps

- **M2S1-G1 — Passive and active evidence cover different devices.** Part A's PCAP is the
  **rack**, but Part B's Nmap and Part C's PowerShell run on the **kit**. W1.2 asks "matches
  passive evidence?", Part C/D ask for one merged profile per device, and reflection Q2 asks what
  active found that passive missed. None of these works unless some devices have *both* kinds of
  evidence. This is the central design question (M2S1-P1, Q1).
- **M2S1-G2 — The M1-S1 rack PCAP is thin for *passive discovery*.** Checked with tshark:
  - It has **no** dhcp, mdns/llmnr/nbns, browser, kerberos/ldap/smb.
  - LLDP comes from only 3 L1 devices (`as410-cstr`, `et200sp-cstr`, `level1switch1`), with no
    system description.
  - SNMP polls only sysUpTime.
  - The S7 frames are setup-communication only (no SZL identity read).
  - There are 3 PROFINET DCP frames.

  So W1.1's **Hostname** column and W1.4's **Firmware / OS** column can't be filled passively from
  it. The only names come from DNS queries.
- **M2S1-G3 — Bug in the M1-S1 PCAP: every DNS A answer is 10.1.20.17** (e.g.
  `wsus.np.local → 10.1.20.17`; it should be 10.1.20.12). This matters little in M1 but breaks
  hostname-to-IP mapping in M2-S1. Fix it in the generator; regenerating M1-S1 changes its
  SHA-256 (M2S1-Q12).
- **M2S1-G4 — SNMP version drift.** The M1-S1 PCAP uses SNMPv2c. The real devices use **SNMPv3
  authPriv** only (NMS onboarding). Under D12 reality wins. That also teaches something:
  authPriv hides the payload, but the cleartext **engine ID** still identifies the vendor.
- **M2S1-G5 — Planted asset carry-over.** The M1-S1 PCAP contains the planted Ewon-style gateway
  (192.168.4.50). If it stays, it becomes part of the M2 "baseline", and Session 2 would need a
  *different* rogue. (M2S1-P9, Q3.)
- **M2S1-G6 — Problems with the Nmap commands in the workbook:**
  1. **S1 and S2 use different host discovery.** S1 uses `--disable-arp-ping`, S2 uses `-PR`
     (ARP). Devices that ignore ICMP/TCP pings (common in OT) will look "New" in S2 and create
     false deviations.
  2. **The S2 port list drops 34962-34964**, so ndiff shows noise.
  3. **UDP services can't be seen.** 161 (SNMP) and 34962-34964 (PROFINET) are UDP services
     scanned with TCP `-sT`. "Closed" there does not mean "not running", which is a teaching
     point, but must be explained.
  4. **Speed.** `-Pn -T2 --scan-delay 200ms` across a whole /24 probes 14 ports on every empty
     address and is slow. The targets must be an explicit host list.
- **M2S1-G7 — `Get-CimInstance Win32_Product` is unsafe on an OT workstation.** Enumerating it
  makes Windows Installer run a consistency check on *every* MSI product. That takes minutes,
  logs event 1035 per product, and can trigger a self-repair. On a PCS 7 engineering station that
  is a real risk. Replace it with a read of the Uninstall registry keys (M2S1-P5).
- **M2S1-G8 — Kit facts unknown:**
  - IPs (drawing only), SC646 management IP, VLAN IDs, gateway.
  - Whether the scan host can reach the control VLAN *through* the SC646.
  - Whether Nmap is on the EWS.
  - The EWS OS and the account students use.
  - Whether all 8 kits are identical.

  The kits are unreachable from MC01 by design (S2-D6), so the operator must supply these.
- **M2S1-G9 — Firmware/OS versions for the lifecycle register.**
  - **Known:** WAM763-1 V03.02.00; PAN-OS 11.1; FortiOS 7.4; DMZ/L3 VMs are Windows Server 2022;
    SINEC NMS V3.0.
  - **Unknown to Claude:** every kit device (CPU 410, ET 200SP, XC208G, SC646) and the rack's L1/L2
    devices (rule 13). The M1 answer book's "PCS 7 V9.1" has no recorded source.
- **M2S1-G10 — Lifecycle research needs internet, and the facts move over time.**
  - Kits have no internet, so research happens on BYOD (D5). It is the slowest part of the
    session.
  - The vendor facts are time-sensitive. Example to verify: Windows Server 2022 mainstream
    support is believed to have ended **2026-10-13**, the day before this tracker was written.
    The answer key must be re-checked before each cohort.
- **M2S1-G11 — The workbook contradicts D5.** It says "never paste … full internal IP schemes"
  into an external AI; D5 says lab IPs may be pasted. D5 is the operator's rule. The trainer must
  say so explicitly or students will hesitate.
- **M2S1-G12 — Time budget.** Seven tables, two scans and web research in 120 min, with one
  trainer. W1.5 (lifecycle) and W1.4 (12-row merge) are the heavy ones.
- **M2S1-G13 — Session 2 depends on this design.** S2 re-runs the same discovery "on the same
  monitor point" and diffs. So the S1 rack PCAP, the Nmap method and the approved targets must be
  reproducible in S2. Design the S1 and S2 rack captures from **one spec**, with S2 adding the
  deltas.
- **M2S1-G14 — The M1 baseline must be to hand.** Students need their M1-S1 inventory. A student
  who missed M1, or a lost bundle, needs a fallback: the M1 answer book's W1.1/W1.2, issued as
  "the M1 baseline".
- **M2S1-G15 — HMI and Engineering Station are one VM on the kit**, while the Parameter Sheet has
  separate `<HMI_WS_IP>` and `<ENG_STATION_IP>`. Pre-fill both with the same IP and add a note.
- **M2S1-G16 — Active scanning of the kit's CPU 410 and ET 200SP.** A TCP connect to 102/80/443
  is normal engineering traffic, but the workbook wants the trainer to explicitly list fragile
  devices. The trainer must decide whether the CPU 410 and ET 200SP are in scope.

## 7. Proposals (not decided)

- **M2S1-P1 — DECIDED (M2S1-D1). Evidence scope: the kit is the merge target; the rack is passive plus M1.**
  - **Kit devices (5):** all three sources.
    - *Passive:* a 5-minute Wireshark capture on the EWS's own NIC. It needs no switch change
      and still sees EWS↔PLC traffic, ARP, XC208G LLDP and PROFINET DCP multicast. The pair's
      M1-S2 SPAN capture can be added if it is still in their bundle.
    - *Active:* Nmap.
    - *Host:* EWS PowerShell.
  - **Rack devices:** the rack PCAP (P) plus the M1 inventory (M1). They have no A or H source, so
    their confidence is lower.
  - This gives the **Confidence Report (W1.6) its lesson: confidence follows the number and kind
    of independent sources**. It also makes reflection Q2 answerable on the kit.
  - *Optional add-on:* M2S1-P10 gives some rack assets a host source too.
- **M2S1-P2 — DECIDED as a design, not built now (M2S1-D2). A new rack PCAP, `TR-M2S1-rack-passive.pcapng`.** Built from the M1-S1 spec with a
  **passive-identity layer** added, so every W1.1 column can be filled from the wire.
  - **Hostnames:** NBNS/LLMNR from Windows hosts (defaults on Server 2022; a hardened host stays
    silent, which is a finding). Kerberos AS-REQ carrying the client name. **Correct** DNS
    answers (G3).
  - **Firmware / model:** LLDP from every SCALANCE switch with sysName + sysDescr (model and
    firmware); PROFINET DCP Identify responses (NameOfStation, vendor/device ID); one S7 **SZL
    0x0011** read by ES01 that returns the CPU 410 order number and firmware.
  - **Reality checks:**
    - SNMPv3 authPriv (G4).
    - **No DHCP** (static lab) and **no `browser`**: the Computer Browser service is gone on
      Server 2019 and later. That teaches that "an empty filter is also a result".
  - **Session 2 hook:** the same spec, with deltas, produces the S2 capture (G13).
  - Same rules as M1-S1: real stacks on 127.0.0.1, zero malformed frames, non-uniform timing,
    SIS silent.
- **M2S1-P3 — Pre-filled Kit Parameter Sheet per kit.** Rack and central values come from §5.1;
  the operator checks the kit values once. This saves 5–10 minutes (same as M1-S1 M5).
- **M2S1-P4 — One "standard scan" approved in the briefing** (same pattern as M1-S2 S2-P3):
  - `<APPROVED_TARGETS>` = the explicit kit host list.
  - The same host-discovery method in S1 and S2. Recommended: ARP (`-PR`) on the scan host's own
    segment.
  - The same port list in both sessions, **plus 3389** (M2S2-D3: S2's K2 enables RDP on the
    EWS and the scan must be able to see it; the list must already include it in S1).
  - **The scan host is not Kali** (M2S2-G6): Kali must be absent from the S1 baseline so it can
    appear as "New" in S2. M2-S2 proposes the kit host OS (M2S2-P7).
  - The port scan runs in the background while the pair does Part C.
  - A one-line explanation that 161 and 34962-34964 are UDP.
  - The trainer initials each pair's card. The workbook command changes go on a "trainer
    substitutions" slip.
- **M2S1-P5 — Replace `Win32_Product` with the Uninstall registry keys**, and provide one
  read-only script, `Collect-HostEvidence.ps1`. It runs every Part C command, writes
  `M2-W1-<KIT_ID>-05-host-*.txt`, and hashes the files. This saves typing time and removes the
  MSI-repair risk (G7).
- **M2S1-P6 — Keep the lifecycle register to ~8 assets:** the 5 kit devices plus 3 rack picks
  (one Windows Server 2022 VM, the PA-440 on PAN-OS 11.1, the WAM763-1 on V03.02.00).
  - Hand out a **vendor-sources card** with starting URLs (ProductCERT, SIOS, Microsoft
    Lifecycle, Palo Alto EoL), but no answers.
  - Claude builds the answer key from vendor pages and re-checks it before each cohort (G10).
- **M2S1-P7 — Where the AI is expected to slip.** These cover the "≥ 2 AI errors" deliverable:
  1. Invented or wrong Siemens advisory IDs (SSA-xxxxxx) or CVEs for the CPU 410 / SCALANCE.
  2. Wrong support dates, e.g. Windows Server 2022 "in mainstream support"; CPU 410 called EoL
     because it is confused with the S7-400 phase-out.
  3. From the passive summary: labelling every Windows host an "HMI", or inferring a DHCP server
     that isn't there.

  All three to be confirmed in a dry run with a real AI chat.
- **M2S1-P8 — Run-sheet outline** (detailed in CLASSROOM_PLAN later):

  | Time | Trainer | Pairs |
  |---|---|---|
  | 0:00–0:10 | Brief: scenario, safety, D5 vs workbook AI wording (G11), standard scan (P4) | Pre-flight; start the 5-min kit passive capture |
  | 0:10–0:15 | Projector: rack capture points on the drawing | Watch |
  | 0:15–0:35 | Floats | Part A on the rack PCAP → W1.1; AI asset-list step |
  | 0:35–0:40 | Initials scan cards | Start the sweep, then the port scan (background) |
  | 0:40–1:00 | Floats | Part C script → W1.3; W1.2 when the scan finishes; AI correlation |
  | 1:00–1:40 | Floats; at ~1:20 checks W1.5 sources | Part D: W1.4 merge, W1.5 research on BYOD, W1.6 |
  | 1:40–1:52 | Floats | W1.7 AI log; hash evidence |
  | 1:52–2:00 | Debrief on the 3 reflection questions | — |

- **M2S1-P9 — SUPERSEDED by M2S1-D3.** *(Was: the M2 baseline capture shows the M1 Ewon as
  removed.)* The operator chose instead to issue the **architecture diagram** as the documented
  baseline, with one **rarely-communicating** device altered on it. Students must infer that
  device from the PCAP's behaviour. Which device, and whether it is removed or misplaced, is
  M2S1-Q19.
- **M2S1-P10 (optional) — Rack host-evidence pack.** Claude collects **read-only** host evidence
  from the in-scope DMZ/L3 Windows VMs through the Lab Console:
  - It uses the same command set as P5, with no `Win32_Product`.
  - Output is sanitised: no secrets.
  - It is handed out as files, so some rack assets get an H source and real patch levels.
  - L2 hosts (OSS01, ES01) are excluded (rule 13).
  - It needs the operator's go-ahead (rule 14).

## 8. Open questions

| # | Question | Status |
|---|---|---|
| M2S1-Q1 | Evidence scope: accept P1 (kit = full P/A/H merge; rack = passive + M1)? | **DECIDED (M2S1-D1)**. P10 add-on still open (Q9) |
| M2S1-Q2 | New rack PCAP with a discovery layer (P2), or reuse the M1-S1 PCAP as-is? | **DECIDED (M2S1-D2)**: assume the P2 capture exists; don't build it now |
| M2S1-Q3 | Ewon in the M2 baseline: removed (P9) or kept as accepted risk? | **SUPERSEDED (M2S1-D3)**: see Q19 |
| M2S1-Q4 | Kit facts: confirm IPs (drawing), SC646 mgmt IP, VLAN A/B IDs, gateway. Can the scan host reach VLAN A through the SC646? All 8 kits identical? (overlaps M1 Q6, S2-Q1) | DEFERRED (operator: students will have access; design first) |
| M2S1-Q5 | Scan host: Kali VM or EWS VM? Is Nmap installed there? Are the CPU 410 and ET 200SP approved targets? | DEFERRED |
| M2S1-Q6 | EWS VM: Windows version, the account students use, local admin or not? | DEFERRED |
| M2S1-Q7 | Firmware/OS versions: kit CPU 410, ET 200SP, XC208G, SC646 and the rack L1 devices for the PCAP. Supply real values, or should Claude pick plausible ones marked `synthetic` in the spec? | DEFERRED (with the PCAP, M2S1-D2) |
| M2S1-Q8 | May the trainer substitute workbook commands (P4 scan alignment, P5 registry instead of `Win32_Product`)? | OPEN |
| M2S1-Q9 | P10: may Claude collect read-only host evidence from DMZ/L3 Windows VMs? | OPEN |
| M2S1-Q10 | Lifecycle register scope (P6): 5 kit + 3 rack assets OK? | OPEN |
| M2S1-Q11 | Kit passive source: 5-min EWS-NIC capture, the M1-S2 SPAN capture, or both? | OPEN |
| M2S1-Q12 | Fix the M1-S1 PCAP DNS bug (G3) now? This regenerates M1-S1 and changes its SHA-256 and answer-book header | OPEN (independent of M2; affects M1-S1 only) |
| M2S1-Q13 | SNMP in the new PCAP: v3 authPriv, matching reality (G4)? | DEFERRED (with the PCAP) |
| M2S1-Q14 | Pedagogical focus for M2: evidence quality and confidence (not D11-style familiarisation)? | PROPOSED in the design review §2 |
| M2S1-Q15 | Design review §4: reframe Part A as **diagram-vs-wire reconciliation** with three buckets (documented & seen / documented, not seen / seen, not documented)? | OPEN |
| M2S1-Q16 | Design review §5: interaction shape of **3 demos** (capture points, scan footprint, lifecycle lookup), **1 gate** (scan card) and **2 checkpoints**? | OPEN |
| M2S1-Q17 | Design review §6: student appendices **A–F** + scan card + W1.4 CSV/XLSX template: all, or a subset? | OPEN |
| M2S1-Q18 | Design review §4 Part D: lifecycle register on **4–5 deliberately different assets** instead of all; AI correlation step folded into W1.4 drafting? | OPEN |
| M2S1-Q19 | Planted device (M2S1-D3): which device, and is it **removed** from the diagram or **misplaced** on it (documentation drift)? Candidates: L2BM_B&R / Veeam (one backup job in the window; also sets up S4), ES01 (one engineering session + DCP scan, otherwise silent; but students know it from M1) | OPEN |
| — | Carried over from M1, still open there: evidence store (M1 Q10 / L2), AI device and text transfer (Q16 / L1), Wireshark version on kits (Q27), kit reset between cohorts (Q12) | OPEN (M1) |

## 9. Prep task list

Added as decisions land.

| # | Task | Owner | Status |
|---|---|---|---|
| — | — | — | — |

## 10. Build status

**Not built (M2S1-D2).** Materials are written as if `TR-M2S1-rack-passive.pcapng` exists with
the P2 content. Consequence: answer-book values that depend on it (frame numbers, counts,
periods) are marked **provisional** until the capture is built and checked with tshark (the
prep prompt's "numbers must be real" rule). When it is built: spec
`tools/lab-pcap/spec/m2s1.yaml`, validation gate (0 malformed, expected protocol hierarchy),
SHA-256 recorded here and in the answer book.

## 11. Decision log

| ID | Date | Scope | Decision | Rationale |
|---|---|---|---|---|
| M2S1-D1 | 2026-10-14 | M2 S1 | **Evidence scope (P1):** the kit's devices get passive (own-seat capture), active (Nmap) and host (PowerShell) evidence and are the merge target. Rack devices get the rack PCAP + the M1 inventory only | Operator. Makes the merge and reflection Q2 possible; the confidence gap between kit and rack rows becomes the lesson |
| M2S1-D2 | 2026-10-14 | M2 S1 | **Rack PCAP (P2):** assume `TR-M2S1-rack-passive.pcapng` exists with the discovery layer described in P2. **Do not build it now**; it will exist once the lab is ready | Operator. Materials are written against the P2 design; dependent answer values are provisional (§10) |
| M2S1-D3 | 2026-10-14 | M2 S1 | **Planted device:** students receive the **architecture diagram** as the documented baseline. One device that communicates **only a few times** is altered on it, so it must be **inferred from behaviour in the PCAP**, not read off directly. Replaces P9 | Operator. Turns Part A into reconciliation, not re-enumeration. Device and form of alteration are Q19 |

## 12. Changelog

- 2026-10-14: Tracker created. Read M2 Session 1 end to end and mapped it to the lab. Checked the
  M1-S1 PCAP with tshark for passive-discovery content and found it thin (G2), with a DNS-answer
  bug (G3). Listed gaps G1–G16, proposals P1–P10 and questions Q1–Q14.
- 2026-10-14: Operator agreed P1 (D1), chose to assume the P2 capture exists without building
  it (D2), and replaced P9 with a planted device altered on the architecture diagram (D3). Kit
  specifics (Q4–Q7) deferred: design comes first. Wrote `ACTIVITY_DESIGN_REVIEW.md` (verdict,
  problems, part-by-part reframing, trainer–student interaction, appendices A–F, alternatives)
  and added Q15–Q19.
- 2026-10-14: M2-S2 prep started (`Lab-Modules/M2-S2/`). It constrains S1: P4 now carries 3389
  in the standard port list (M2S2-D3) and a "scan host is not Kali" rule (M2S2-G6). Kali VM
  must be powered off on every kit throughout S1 (M2-S2 STAGING_LOG §1).
