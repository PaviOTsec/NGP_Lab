"""Phase 6: FW-North (FortiOS 7.4) — SNMPv3 user, SNMP agent on, snmp on port4 allowaccess
(existing list kept), NTP 10.1.20.21, timezone Asia/Singapore. Line by line; on the first error
send `abort` (discards the uncommitted edit/config block) and stop. Secrets masked.
usage: python -I nms_apply_fortigate.py <backend_dir> <out_dir>"""
import asyncio
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
NAME, IP, FP = "FW-North", "10.4.20.254", "SHA256:38yWadbTq3bsXJFjMcoZJXDW1lafIZba2ZdYNNiamek"
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"FortiGate[\w-]*( \([\w-]+\))? [#$]\s*$")
ERROR = re.compile(r"(?i)command fail|parse error|unknown action|not found|invalid|error|entry not")
EXPECT_ALLOWACCESS = "ping https ssh http"   # read in phase 1; verified again below before changing

COMMANDS = [
    "config system snmp sysinfo", "set status enable", "end",
    "config system snmp user", 'edit "sinecnms"', "set queries enable", "set security-level auth-priv",
    "set auth-proto sha256", "set auth-pwd {AUTH}", "set priv-proto aes", "set priv-pwd {PRIV}", "next", "end",
    "config system interface", 'edit "port4"', f"set allowaccess {EXPECT_ALLOWACCESS} snmp", "next", "end",
    "config system ntp", "set ntpsync enable", "set type custom", "config ntpserver", "edit 1",
    'set server "10.1.20.21"', "next", "end", "end",
    "config system global", 'set timezone "Asia/Singapore"', "end",
]
VERIFY = ["get system snmp sysinfo", "show system snmp user", 'show system interface port4',
          "show system ntp", "diagnose sys ntp status", "get system global | grep -i timezone",
          "get system status | grep -i 'System time'"]


async def send(proc, cmd, maxwait=40.0):
    proc.stdin.write(cmd + "\n")
    buf, loop = "", asyncio.get_running_loop()
    end = loop.time() + maxwait
    while loop.time() < end:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(65536), timeout=2.5)
        except asyncio.TimeoutError:
            if PROMPT.search(ANSI.sub("", buf).rstrip()):
                break
            continue
        if not chunk:
            break
        buf += chunk
        if re.search(r"--More--", buf[-100:]):
            proc.stdin.write(" ")
    return ANSI.sub("", buf).replace("\r", "")


async def main():
    store = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    login = store.credential("network/admin")
    sec = {"{AUTH}": store.credential("snmpv3/nms").password, "{PRIV}": store.credential("snmpv3/nms-priv").password}
    mask = lambda s: re.sub("|".join(re.escape(v) for v in sec.values()), "********", s)  # noqa: E731
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed = [], None
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        cur = await send(proc, "show system interface port4")
        m = re.search(r"set allowaccess (.+)", cur)
        log.append(">>> pre-check port4\n" + cur.strip())
        if not m or m.group(1).strip() != EXPECT_ALLOWACCESS:
            sys.exit(f"port4 allowaccess is now '{m.group(1).strip() if m else None}', expected '{EXPECT_ALLOWACCESS}' — not changing")
        for tmpl in COMMANDS:
            cmd = tmpl
            for k, v in sec.items():
                cmd = cmd.replace(k, v)
            out = await send(proc, cmd)
            body = out.split("\n", 1)[1] if "\n" in out else ""
            log.append(f">>> {mask(cmd)}\n{mask(body).strip()}")
            print(f">>> {mask(cmd)}")
            if ERROR.search(re.sub(r"(?m)^.*FortiGate.*[#$]\s*$", "", body)):
                failed = mask(cmd)
                print(f"!!! error — sending abort:\n{mask(body).strip()}")
                for _ in range(4):
                    await send(proc, "abort")
                break
        log.append("\n===== VERIFY =====")
        for v in VERIFY:
            out = await send(proc, v)
            log.append(f">>> {v}\n{mask(out.split(chr(10), 1)[1] if chr(10) in out else out).strip()}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_apply-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="nms-phase6.apply-fortigate", target=NAME, transport="ssh",
                                               result="error" if failed else "ok", detail={"stopped_at": failed or ""})
    print(f"\nRESULT: {'STOPPED at: ' + failed if failed else 'all commands accepted'}\ntranscript: {path}")


asyncio.run(main())
