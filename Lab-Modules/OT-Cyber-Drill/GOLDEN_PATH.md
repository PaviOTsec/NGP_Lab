# OT Cyber Drill — The Highlighted Red Pathway ("Golden Path") + Blue Mirror

**White Team only.** The one Red route we fully plan, stage and flag. Other routes in
`RED_BLUE_OPTIONS.md` are left open for students to find. Every stage has a **flag** (Red captures
it) and a **Blue mirror** (detect + stop). Operator's chain, mapped to real lab assets.

Decisions: DD1–DD11. This path = the operator's 2026-10-19 design.

## Scope legend (who stages what)

- 🟢 **REAL in-scope** — real lab asset the console/operator already drives (DMZ 10.1.20.x, L3). I
  can build the supporting pieces (honeyfile, planted creds, Splunk panels).
- 🟡 **SURROGATE** — in-scope stand-in I build offline (no L2/L1 device touched): OT-boundary
  device, EWS, Modbus light PLC, on an **isolated drill segment**.
- 🔴 **REAL L2/L1** — real OT-FW / EWS / PLC. **Rule 13: Claude & the console never touch these.**
  Only the operator stages/runs them, and only with the override passphrase for any help from me.
  **I recommend we do NOT use the real ones — see the safety note at Stage GP-3.**

---

## The chain at a glance

```
 Kali (L5) ─► foothold ─► [PtH] ─► Domain Admin ─► DC (loot password.txt) ─► SINEC INS
   GP-0          seed       GP-1        🟢            🟢 10.1.20.17            🟢 10.1.20.21
                                                  │                              │
                                                  └──► creds to INS ◄────────────┘
                                                         │
          create RADIUS user ─► log in to OT boundary ─► open DMZ→OT ─► EWS ─► Modbus write ─► LIGHT
              GP-2 🟢(INS)          GP-3 🟡/🔴             GP-3           GP-4 🟡        GP-4 🟡 GLOWS
```

Flags: **GP-1** DA hash/session · **GP-2** contents of `password.txt` (INS creds) · **GP-3** RADIUS
user created + DMZ→OT rule committed · **GP-4** the light glows (final flag).

---

## GP-0 — Foothold & the pass-the-hash seed  ·  🟢
**So PtH has something to pass.** Red on **Kali** `L4H1_Attacker_Kali` (L5). Firewall posture:
**L5→DMZ allowed** (operator; matches the existing `L4L5-to-DMZ-L3-AnyPort` allow).

- **Design decision — where the DA hash comes from (pick one):**
  - **(a) Seeded foothold host (recommended, deterministic):** a DMZ member server (e.g.
    `DMZH1_MSSQL` 10.1.20.14) has a **cached domain-admin logon** we plant. Red lands on it (Stage-0
    options in `RED_BLUE_OPTIONS.md`), dumps LSASS/SAM, recovers the **DA NTLM hash**. Clean flag.
  - **(b) Poison + relay:** Responder/ntlmrelayx on a segment where a DA authenticates; capture/relay
    NTLM. More realistic, less deterministic (timing-dependent).
- **Red tool:** mimikatz / secretsdump → DA hash.
- **Blue mirror — detect:** Sysmon EC10 (LSASS access) on the seeded host; ESCU credential-dumping;
  4624 then suspicious access. **Stop:** isolate the host, reset the exposed DA.

## GP-1 — Pass-the-hash → Domain Admin  ·  🟢  ·  T0859 / ATT&CK T1550.002
**Flag GP-1:** an authenticated **DA** session (hash passed, no plaintext).

- **Red:** `pth-winexe` / `evil-winrm -H <hash>` / `secretsdump -hashes` against the **DC**
  `DMZH2_DC` 10.1.20.17 (np.local) — logon **as DA using the hash only**.
- **Blue mirror — detect:** 
  - Splunk `index=wineventlog host=DMZH2DC EventCode=4624 Logon_Type=3` with **NTLM** auth where
    Kerberos is the norm; no preceding 4768/4769 → PtH signature. ESCU **"Pass the Hash / Overpass"**.
  - **Zeek `ntlm.log`** — NTLM auth to the DC from a non-admin workstation.
  - LAB privileged-group / unusual-DA-usage panel.
- **Blue mirror — stop:** disable the DA account; **reset krbtgt** (removes forged-ticket follow-on);
  FW deny the source host; isolate.
- **Teaching:** NTLM-where-Kerberos-should-be is the tell; this is the highest-value Blue catch.

## GP-2 — DA into the DC, loot the honeyfile  ·  🟢  ·  T0811 Data from Information Repositories
**Flag GP-2:** the contents of `C:\Users\Administrator\Documents\password.txt` on the DC — which
names **SINEC INS** 10.1.20.21 and an INS login.

- **Red:** RDP/WinRM/SMB to the DC as DA; read `password.txt`.
- **Build (mine, 🟢):** plant `password.txt` as a **honeyfile** with an **object-access SACL** so any
  read raises Windows **4663** — a high-signal canary. Contents: INS URL + a credential that only
  works on INS (scoped to the drill).
- **Blue mirror — detect:** 
  - **4663** on `password.txt` (the canary) → instant, precise alert (I'll add a LAB alert
    "honeyfile read"). 4624 on the DC from an unusual source. Zeek smb.log file read.
  - Sysmon EC1 (interactive tools on the DC).
- **Blue mirror — stop:** kill the DC session; **rotate the INS credential** named in the file
  (breaks the next stage); isolate the DC.
- **Teaching:** canary/honeyfile detection + "secrets in files" hygiene. A denied GP-2 (rotate the
  INS cred) hard-stops the path → Branch B.

## GP-3 — SINEC INS → RADIUS user → OT boundary → open DMZ→OT  ·  🟢 (INS) + 🟡/🔴 (boundary)
**Flag GP-3:** a **new RADIUS user on INS** + a **committed rule** opening DMZ→OT on the boundary.

- **Red:** 
  1. Log in to **SINEC INS** 10.1.20.21 (web UI) with the looted credential.
  2. **Create a RADIUS user** (INS provides RADIUS/AAA).
  3. Use it to **authenticate to the OT boundary firewall** (RADIUS-backed login).
  4. **Add a rule** allowing **DMZ→OT** (the connectivity that's deliberately absent).
- **Blue mirror — detect:**
  - **INS admin audit** — new RADIUS/AAA user created (INS is in-scope; its audit/syslog → Scribbler
    → `netdev`). I'll add a LAB NET "AAA user created on INS" alert.
  - **Boundary config-change** event → syslog → Scribbler → `netdev` **LAB NET "config change"**;
    RADIUS auth/login event. Zeek/Suricata on the INS web session.
- **Blue mirror — stop:** revoke the RADIUS user on INS; **back out the DMZ→OT rule** (one named
  snapshot to restore); alert-on-config-change as the trip wire.

> ### ⚠️ Safety note — do NOT use the real OT-FW / real L2-L1 here (strong recommendation)
> The real OT firewall is the **SCALANCE SC646-2C** 192.168.20.254. Opening **DMZ→L2** on it bridges
> students into the **real L1 broadcast domain** — the production CPU 410, IEDs, the WAGO, and
> critically the **SIS safety island** (192.168.2.x). That is exactly the L2-adjacency risk already
> on record ([[trainee-wifi-ap-project]]), it is **outside the existing rule-13 OT-FW exceptions**
> (which are SNMP/visibility only, "no ruleset/interface/routing changes"), and students holding DA
> + a firewall opening next to a live safety system is an unacceptable exercise risk.
>
> **Instead (🟡):** the "OT boundary firewall" and everything behind it in the drill is an **isolated
> drill segment** — a surrogate boundary device (or a dedicated drill VLAN gated by a device the
> operator controls, RADIUS-backed by the real INS so steps 1–3 stay real), the **EWS surrogate**,
> and the **Modbus light PLC**, all physically/logically separate from the real L1/L0 cells. To
> students the story is identical ("you opened the OT firewall and reached the EWS"); the real
> safety island is never exposed. I build the surrogate segment offline; the operator wires the
> light. If you nonetheless want the real SC646/EWS/L1 light, that's yours to stage and run under the
> override — and even then: backup-first, observe-what-changes, SIS untouched.

## GP-4 — EWS → Modbus write → the light glows  ·  🟡  ·  T0836 Modify Parameter / Impact
**Flag GP-4 (final):** the **light glows** — a Modbus coil/register written from the EWS.

- **Red:** log in to the **EWS surrogate** (now reachable via GP-3); run the provided script (or a
  Modbus client) that writes the coil driving the indicator on the **drill Modbus PLC**.
- **Build (mine 🟡 + operator wiring):** EWS surrogate with a Modbus client + the script; a small
  **drill Modbus device + LED** on the isolated segment (a real PLC/micro the operator wires, or a
  pure-software indicator on the surrogate HMI if no hardware). pymodbus stack, no real cell.
- **Blue mirror — detect:**
  - **Zeek/Suricata Modbus** — a **write** (FC5/FC6/FC15/FC16) on the OT segment, which read-only
    polling never does. Suricata ET Modbus-write sig; Zeek `modbus.log`.
  - EWS surrogate auth log (4624) + the script's process (Sysmon-equivalent on the surrogate).
  - The **light itself** = the physical ground truth for the AAR.
- **Blue mirror — stop:** deny the OT path / revert GP-3's rule; isolate the EWS; revert the coil.
- **Teaching:** a **Modbus write** is the unmistakable OT-impact signature; read-only vs write is the
  whole lesson. This is the tactile climax — students watch the light they caused go on, and Blue
  watches the write cross the wire.

---

## Flag → gate → scoring (stage-based, DD10)

| Flag | Stage | Red captures | Blue detects | Blue stops (denies flag) | Workbook gate |
|---|---|---|---|---|---|
| GP-1 | PtH→DA | DA session via hash | NTLM-not-Kerberos on DC (Splunk/Zeek) | disable DA, reset krbtgt | ~G3/G4 |
| GP-2 | Loot DC | `password.txt` contents | **4663 honeyfile canary** | rotate INS cred, kill session | ~G5/G8 |
| GP-3 | INS→OT rule | RADIUS user + DMZ→OT rule | AAA-user + config-change (netdev) | revoke user, back out rule | ~G6/G7 |
| GP-4 | Light | coil written, light on | **Modbus write** (Zeek/Suricata) | deny OT path, revert coil | ~G11 |

Branch logic: deny GP-1 (reset DA) or GP-2 (rotate INS cred) = hard **Branch B** stop; later stages
become labelled SIM. GP-3/GP-4 are where process-protection scoring lands.

## Open design decisions (operator)

1. **GP-0 seed:** plant a cached **DA hash** on `DMZH1_MSSQL` (option a, recommended) — OK, or a
   different host / the poison-relay route?
2. **GP-3 boundary — confirm the isolated-drill-segment redesign** (🟡) over the real SC646/L1 (🔴).
   My strong recommendation is the surrogate segment with **real INS RADIUS** so steps 1–3 stay real.
3. **GP-4 light:** real hardware (operator wires a drill PLC + LED, isolated) or software indicator
   on the surrogate HMI? Real hardware is the better "feel" if a safe, isolated unit exists.
4. **INS reachability:** inventory marks INS `access: power-only` (web-only by operator choice). For
   the drill, students need its **web UI + RADIUS**; confirm that's enabled for the exercise.
