# OT Cyber Drill — Red Options × Blue Counters, by Stage Flag

**White Team only.** The option tree for the drill: every realistic Red path **in our lab**, and
for each, how Blue **detects** and **stops** it on the real stack. You'll turn each stage into a
concrete **flag** and make the options real; this file is the map from offense → flag → defense.

Decisions in force: DD1–DD7. Updates from 2026-10-19 (operator):
- **Red starts on Kali (L5), earns the RAC foothold** (new Stage 0) rather than starting on RAC.
- **SSM dropped; Zeek + Suricata** provide network visibility on the drill path (SPAN of L5 +
  FW-South transit assumed). "All the visibility Blue wants" — so network-IDS detections are in play.
- **Historian has a credential** (DQ5) → Stage 8/12 can be live against the real `L3H1_Historian`.

## The flag model

- A **flag** is a concrete artifact proving a stage was reached — a captured value, a session, a
  file hash, a changed setpoint. Red *captures* it; Blue *mirror-captures* the detection and may
  *deny* it (stop the stage). One stage = one gate in the workbook (G1…G12).
- **Red score** = flags captured + evidence discipline. **Blue score** = stages detected + stages
  stopped + process protected (the workbook's /100 split still applies).
- **Branch logic falls out of the flags:** a denied flag = **BLOCK** (Branch B) → later stages run
  as labelled SIM counterfactuals. A telemetry gap = **Branch C** (score not-assessable, issue the
  alternate packet). Exactly the workbook's model, now participant-driven.

## Lab assets Red can use / Blue can watch

| Red launch / pivot | Blue telemetry & consoles | Blue containment levers |
|---|---|---|
| Kali `L4H1_Attacker_Kali` (L5, NIC attached for drill) | **Splunk** wineventlog / sysmon / netdev + LAB/ESCU/LAB NET alerts | Disable `drill-svc` (DC/host) |
| Win attacker 10.5.20.205 (L5) | **Zeek** conn/dns/ssl/rdp/ntlm/smb/weird logs | FW-North / FW-South deny rule (drill posture, DD2) |
| RAC `L4H1_RAC` 10.5.20.10 (L5, **UF+Sysmon**) | **Suricata** ET sigs (scan/exploit/C2/brute) | Kill RDP/WinRM session; host firewall isolate |
| Mail `L4H1_MailServer` 10.4.20.21 (phish delivery) | **FortiGate FW-North** + **PAN FW-South** → Scribbler → `netdev` | Block Kali/RAC IP at FW-North |
| MaintServer `DMZH2_MaintServer` 192.168.30.11 (**UF+Sysmon**, pivot) | **Historian** read audit (real, pw set) | Disable switchport / NIC on MaintServer |
| Eng-station **surrogate** (we build, through FW-South) | **CSTR surrogate** change audit + live trend | Reset surrogate baseline; revoke firewall path |
| CSTR **surrogate** (we build) | **SINEC NMS** asset/topology (no SSM) | Pull the exercise account's Kerberos/TGT (DC) |

Rule 13 unchanged: the real L2/L1/L0 (ES01, OSS01, CPU 410, SIS, pharma cell) is **never** a target.
The eng-station and CSTR are in-scope surrogates reached *through* the real FW-South.

---

## STAGE 0 — Foothold on RAC (new) · Gate G1a · ATT&CK T0817/T0865/T1110
**Flag F0:** an interactive session / shell on `RAC` 10.5.20.10 as a valid user.

| # | Red option (in our lab) | Blue detects | Blue stops |
|---|---|---|---|
| 0a | **Phish via Mail Server:** payload email to the RAC user; macro/LNK calls back from RAC | Sysmon EC1 on RAC (Office→powershell/cmd parent chain); Zeek http/ssl beacon from 10.5.20.10; Suricata ET malware/C2 sig; Splunk ESCU "suspicious parent" | Block the callback dest at FW-North; disable the user; isolate RAC host firewall |
| 0b | **RDP credential attack:** hydra/crowbar on RAC:3389 from Kali | RAC **4625** burst then **4624** (LAB brute-force alert, 5+ fails same host); Zeek **rdp.log** many attempts; Suricata RDP brute sig | FW-North deny 10.5.20.x→RAC:3389; lock the account (LAB lockout) |
| 0c | **LLMNR/NBT-NS poisoning + relay** (Responder/ntlmrelayx) on L5 | Zeek **ntlm.log** anomalous auth; Suricata Responder/relay sig; Windows 4624 NTLM from unexpected source | Disable LLMNR/NBT on L5 hosts (drill hardening); segment Kali off |
| 0d | **Exploit an exposed RAC service** (if unpatched SMB/RDP) | Suricata exploit sig; Zeek weird.log; Sysmon crash/new-service EC on RAC | Patch/virtual-patch at FW-North; isolate RAC |

**Teaching:** enterprise foothold is where host + network IDS overlap most — the easiest Blue win,
best as the opening. Capturing F0 proves Red controls RAC; Blue denying it = Branch B from the start.

## STAGE 1 — Pivot to the OT boundary · Gate G1 · T0822 External Remote Services
**Flag F1:** an authenticated session on `MaintServer` 192.168.30.11 from RAC.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 1a | **RDP/WinRM from RAC → MaintServer** with `drill-svc` | MaintServer **4624** (type 10/3), LAB logon panel; Zeek rdp/ smb; **FW-North allow unlogged by default** (DG3) — enable drill allow-logging if you want it in `netdev` | Disable `drill-svc`; FW-North/South deny RAC→Maint; kill session |
| 1b | **Pass-the-hash / token** reused from Stage 0 | 4624 NTLM, no preceding Kerberos; Zeek ntlm.log | Reset `drill-svc` creds; revoke sessions |
| 1c | **SMB/admin-share exec** (psexec-style) RAC→Maint | Sysmon EC1 `PSEXESVC`/service create (LAB new-service); Zeek smb.log + 5145 share access | Block 445 RAC→Maint; isolate Maint |

**This is the IT→OT boundary** — the moment the workbook's "approved pivot" happens for real.

## STAGE 2 — Execution & host recon on MaintServer · Gate G2 · T0807 Command-Line
**Flag F2:** output of a recon command captured from MaintServer (host/user/network enum).

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 2a | `whoami /all`, `systeminfo`, `ipconfig`, `net group` | Sysmon EC1 full command line → Splunk; ESCU discovery detections | Isolate host; terminate session |
| 2b | **PowerShell recon** (AD/host) | 4104 script-block (LAB suspicious-PowerShell keyword list); Sysmon EC1 | Constrained-language / isolate |
| 2c | **BloodHound/SharpHound** collection (if AD reachable) | Heavy LDAP in Zeek; ESCU SharpHound; 4662 | Block LDAP from Maint; disable account |

## STAGE 3 — Persistence / valid-account reuse · Gate G3 · T0859 Valid Accounts
**Flag F3:** a second independent session, or a persistence mechanism, on MaintServer.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 3a | Second sign-in with `drill-svc` | 2× 4624 distinct logon IDs (LAB logon) | Disable account; kill both sessions |
| 3b | **New service / scheduled task** for persistence | LAB **new-service** / **scheduled-task** (4698) alerts; Sysmon EC1 | Remove the service/task; isolate |
| 3c | **Run-key / startup** persistence | Sysmon EC13 registry; ESCU autostart | Remove key; host sweep |

## STAGE 4 — Privilege · Gate G4 · T0890 Exploitation for Priv-Esc
**Flag F4:** proof of elevated context — **OR**, if kept SIM, correct attempt-vs-success call.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 4a | **Real local priv-esc on the surrogate host** (misconfig we plant: unquoted service path / weak ACL) | Sysmon EC1 SYSTEM-context child; 4672; ESCU priv-esc | Fix the misconfig; isolate |
| 4b | **PAPER-SIM** (default for the real hosts): labelled attempt event, **no** 4672 | the *absence* of 4672 is the tell — Blue must record "attempt, not success" | n/a — evidence-discipline flag |

**Note:** 4a is only on the **surrogate**, never a real host, so a real exploit stays rule-13/scope-safe.
Pick 4a if you want Red to earn it; 4b keeps it as the workbook's discipline test.

## STAGE 5 — Defense evasion / masquerade · Gate G5 · T0849 Masquerading
**Flag F5:** an inert file on an authorised path whose **name ≠ provenance/hash**.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 5a | Drop `maint_update_q4.ps1` (inert) on a maintenance path | Sysmon **EC11** FileCreate; hash recorded; Zeek smb file-xfer | Quarantine file; block the path; hash-ban |
| 5b | **Rename a tool to a trusted name** (e.g. `svchost.exe` in temp) | Sysmon EC1 image-vs-path mismatch; ESCU masquerade | Kill process; remove file |

## STAGE 6 — Discovery of the OT target · Gate G6 · T0846 Remote System Discovery
**Flag F6:** a scan result naming the **eng-station surrogate** (open 102/502/3389) from MaintServer.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 6a | `nmap -sT -Pn -p102,502,80,443,3389 <ENG_SURROGATE>` (named host only) | **FW-South** allow/deny → `netdev` (LAB NET sweep); **Suricata** scan sig; **Zeek** conn.log fan | FW-South deny Maint→OT; alert-driven account disable |
| 6b | **PROFINET/DCP or S7 discovery** (snap7 "list blocks", `plcscan`) | Zeek/Suricata OT-protocol sig; netdev OT-source alert | Deny 102 at FW-South |
| 6c | **Broad sweep** (out of scope) | netdev **scan burst**; Suricata; **triggers FREEZE** | FREEZE + Blue BLOCK credit |

**Scope flag:** 6a earns F6; 6c is a deliberate discipline trap — scanning beyond the named host is
penalised and may FREEZE. Good Red takes 6a/6b.

## STAGE 7 — Lateral movement across FW-South · Gate G7 · T0886 Remote Services · **BLOCK showcase**
**Flag F7:** a connection established to the eng-station surrogate **through FW-South**.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 7a | RDP/SSH/S7 Maint→surrogate across FW-South | With **drill posture**: allow→surrogate host log + Zeek; if contained → **FW-South deny → netdev LAB NET "unauthorized connection through firewall"** | FW-South rule Maint→OT deny (the decisive stop); revoke path |
| 7b | **Tunnel/port-forward** through MaintServer | Zeek long-lived conn / unusual port; Suricata tunnel sig | Kill session; deny egress |

**This is the pivotal gate.** Firewall telemetry that was silent at Stage 1 (allow unlogged) now
pays off on the **deny**. If Blue has contained upstream, F7 cannot be captured → Branch B, OT stages
become SIM.

## STAGE 8 — Collection: process/historian view · Gate G8 · T0801 Monitor Process State
**Flag F8:** a captured batch value for PB-2027-091 (read-only) from the **real Historian** (pw set) or surrogate.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 8a | Read a trend/tag from `L3H1_Historian` 192.168.30.10 | **Historian read audit** (now live); Zeek conn to .10; netdev | Disable the read account; FW rule L3 deny |
| 8b | **OPC UA / SQL historian query** | Zeek ssl/ opcua; 4624 on Historian; Sysmon EC3 | Block the port; isolate Historian |

## STAGE 9 — C2 / data channel · Gate G9 · T0885 Commonly Used Port
**Flag F9:** one established beacon/connection to a recorded destination on a common port.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 9a | HTTPS/DNS beacon from the pivot (benign, recorded) | **Zeek** dns.log beacon cadence / ssl JA3; **Suricata** C2 sig; netdev | FW egress deny; sinkhole DNS |
| 9b | Reverse shell on a common port (443/53) | Zeek conn long-lived; Suricata; Sysmon EC3 | Kill; block dest |

## STAGE 10 — Inhibit response / alarm · Gate G10 · T0878 Alarm Suppression · **PAPER-SIM**
**Flag F10:** correct independent-verification call on a missing-alarm SIM sequence.

- **Red:** nothing live (never suppress a real safety alarm). White delivers `EVID-INJ10-ALARM` +
  the independent operator record.
- **Blue detects/stops:** notice the expected alarm is absent, **seek independent verification**,
  state uncertainty — the flag is the *discipline*, not a block.

## STAGE 11 — Impact: modify CSTR parameter · Gate G11 · T0836 Modify Parameter · **tactile climax**
**Flag F11:** one **non-safety** setpoint on the **CSTR surrogate** changed (approved), trend moves.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 11a | snap7/Modbus write to the agitation setpoint on the surrogate (after G11 approval) | **Surrogate change audit** (before/after); live **trend shift**; Zeek OT-write; Suricata S7/Modbus-write sig | Revert setpoint; FW deny OT-write; isolate surrogate |
| 11b | **Write via the eng-station surrogate** (download a changed value) | eng-station audit; OT-protocol write on the wire | Same; plus revoke eng-station path |

**Blue's real job here is process protection:** detect the change, judge batch risk, recommend
pause/degrade, advise Gold. The real pharma cell is never touched (rule 13). Setpoint rolled back at G14.

## STAGE 12 — Manipulation of view · Gate G12 · T0832
**Flag F12:** a trend/record conflict Blue must reconcile and decide batch disposition on.

| # | Red option | Blue detects | Blue stops |
|---|---|---|---|
| 12a | White injects a surrogate-historian vs operator-record discrepancy | compare historian trend vs **independent operator record**; netdev/host audit of the write | Trust the independent record; recommend hold/release PB-2027-091 |

---

## How to turn this into flags (what I'd build next)

1. **Flag registry** `flags.md`: F0–F12, each with the exact artifact string/value, where it lives,
   how Red proves capture, and the Blue detect+stop criteria (= the scoring key).
2. **Make the options real** (your side + mine):
   - Mine (offline/in-scope): CSTR + eng-station surrogates; the planted Stage-0 phish + Stage-4
     misconfig (surrogate only); the inert file; `drill-svc`; the two SIM packets; new Splunk panels.
   - Yours/supervised: drill firewall posture (FW-North/South), Zeek+Suricata sensor on the SPAN,
     Historian password, Kali NIC attach.
3. **Map options → gates → scoring:** each flag = one gate check; Red captures / Blue detects+denies
   are the two scoreboards; the workbook's /100 rubrics map straight onto the flag list.

**Open for you:** (a) which Stage-4 route — real priv-esc on the surrogate (11a-style, earnable) or
keep it SIM; (b) confirm the Zeek/Suricata SPAN placement (L5 + FW-South transit) so I spec Blue's
searches against the right log paths; (c) do you want Stage-0 to default to the **phish** path (most
realistic, uses the Mail Server) as the primary, with RDP-brute as the alternate?
