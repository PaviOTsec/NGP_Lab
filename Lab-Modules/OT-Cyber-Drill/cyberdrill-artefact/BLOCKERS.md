# Drill build — blockers needing an operator change (2026-10-20)

Things blocking the live build that need a host/network change. Each notes the exact fix.

## B1 (primary) — Trellix quarantines the LSASS dump on RAC
- **Symptom:** `comsvcs MiniDump` of lsass **succeeds** (wrote ~50 MB to `C:\Windows\Temp\lb.dmp`),
  but Trellix Endpoint Security then **locks and deletes** the dump before it can be read
  (first a "access is denied" on read, then the file is gone). So credential *extraction* can't
  complete, even though dumping is technically possible (no LSA Protection / no Credential Guard /
  Defender RTP off).
- **Why it matters:** GP-1 ("Red steals the admin hash from RAC") can't be demonstrated reliably
  until the dump can be retrieved.
- **Fix options (operator):**
  1. **Trellix ENS exclusion for the drill** on RAC — exclude the drill dump path/process (e.g.
     `C:\Windows\Temp\lb.dmp`, or the tool), set via ePO (10.1.20.11) or locally. Simplest for a
     deterministic guide. *(Keep Sysmon on — Blue still detects the behaviour; this only stops the
     quarantine so Red's step completes.)*
  2. **Disable Trellix on-access scanning on RAC** for the exercise window.
  3. Leave it on and make **EDR-evasion part of Red's challenge** (realistic for capstone, but
     non-deterministic — not ideal for the scripted golden path / guide capture).
- **Recommendation:** option 1 (narrow exclusion) for the build + guide; mention EDR as a real
  obstacle in the Red notes.

### "Cyber Drill" Trellix policy — exact settings (observed alert: `JTI/Suspect.524610`)
Two different Trellix modules block two different drill steps — relax **both** in a dedicated
policy set assigned to RAC. In **ePO (https://10.1.20.11:8443) → Policy Catalog**, duplicate each
policy below to a copy named "Cyber Drill", change the settings, then assign them to RAC.

1. **Endpoint Security Adaptive Threat Protection → Options** — *this is what fired JTI/Suspect
   on `powershell.exe` (the reverse shell).*
   - Uncheck **Enable Adaptive Threat Protection** (simplest), **or** keep it on and set:
     **Real Protect – client-based** = Off, **Real Protect – cloud-based** = Off,
     **Dynamic Application Containment** = Off, and every **Rule Assignment** reputation action =
     **Observe** (not Block/Clean).
2. **Endpoint Security Threat Prevention → Exploit Prevention** — *blocks the LSASS credential-theft
   behaviour (GP-1 dump) and suspicious-script signatures.*
   - Uncheck **Enable Exploit Prevention**, **or** set the action for all severities to **Report**.
3. **Endpoint Security Threat Prevention → Access Protection** — *protects LSASS / system processes.*
   - Uncheck **Enable Access Protection**, **or** set rules to **Report**.
4. **Endpoint Security Threat Prevention → On-Access Scan** — *quarantined the `lb.dmp` and scans the
   downloaded HTA.*
   - Set **McAfee/Trellix GTI** = **Disabled**, and either disable On-Access Scan or add
     **Exclusions**: `C:\Windows\Temp\`, the user Downloads folder, and processes
     `powershell.exe`, `mshta.exe`, `rundll32.exe`.

**Assign + apply:** System Tree → put RAC in a "Cyber Drill" group (or select RAC) → **Assign
Policies** → point the four policies at the "Cyber Drill" copies. Then force a pull on RAC:
`"C:\Program Files\McAfee\Agent\cmdagent.exe" /p /e` (or ePO → Wake Up Agents). Keep the McAfee
Agent itself running so ePO still manages the box.

- **Minimal:** #1 alone stops the reverse-shell alert; #2+#3+#4 are additionally required for the
  LSASS dump. We need the whole chain, so apply all four.
- **Blue is unaffected:** Trellix events are not a Splunk data source here, so relaxing it loses no
  Blue telemetry — Sysmon + Suricata carry the detections.

## B2 (secondary, firewall) — RAC SMB 445 is filtered
- **Symptom:** `445/tcp` on RAC (10.5.20.10) is filtered from **both** Kali (10.5.20.50) and MC01
  (10.1.20.56) — RAC's domain-profile Windows Firewall. Confirmed `MC01->RAC:445 = False`.
- **Why it matters:** forces the slow base64-over-WinRM path for moving the dump, and blocks
  standard remote credential-dump tooling (nxc `--lsa`, lsassy, remote secretsdump) that needs 445.
- **Fix (operator, optional):** allow inbound 445 on RAC from the drill management host(s) (MC01
  and/or Kali) — a Windows Firewall rule on RAC, or scope it to the drill subnet. Then dump
  retrieval is a fast SMB copy and remote dumpers work.
- **Note:** not strictly required if B1 is fixed (I can still pull over WinRM), but it makes the
  build and the real Red workflow much smoother.

## Already working (for reference — no change needed)
- Kali ↔ RAC same subnet; RAC domain-joined; DC/NMS/INS reachable from Kali on the needed ports.
- LSASS dump *creation* works (no LSA Protection, no Credential Guard).
- Pass-the-hash into NMS works (`Pwn3d!` over SMB + WinRM) — `STAGE2_PTH_CONFIRM.txt`.
- Seed `np\svc_backup` (Domain Admin) resident on RAC — `STAGE2_SEED.md`.
