"""FW-North (FortiOS 7.4): remote syslog to Scribbler 10.1.20.13 (UDP 514), sent from the port4
management address 10.4.20.254 (so Scribbler lists it under its known IP; FW-South admits that source
via L4L5-to-DMZ-L3-AnyPort). Pre-check: syslogd must still be `status disable` (as read 2026-10-19).
Line by line; on the first error `abort` (discards the uncommitted block) and stop.
Rollback: config log syslogd setting / set status disable / end
usage: python -I fortigate_syslog.py <backend_dir> <out_dir>"""
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
COMMANDS = ["config log syslogd setting", "set status enable", 'set server "10.1.20.13"', "set mode udp",
            "set port 514", "set facility local7", 'set source-ip "10.4.20.254"', "end"]
VERIFY = ["show full-configuration log syslogd setting", "show full-configuration log syslogd filter"]


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


def body(out: str) -> str:
    return re.sub(r"(?m)^.*FortiGate.*[#$]\s*$", "", out.split("\n", 1)[1] if "\n" in out else "").strip()


async def main():
    login = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed, verified = [], None, False
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        cur = body(await send(proc, "show full-configuration log syslogd setting"))
        log.append(">>> pre-check\n" + cur)
        if "set status disable" not in cur:
            sys.exit("syslogd is no longer 'status disable' - not changing:\n" + cur)
        for cmd in COMMANDS:
            b = body(await send(proc, cmd))
            log.append(f">>> {cmd}\n{b}")
            print(f">>> {cmd}" + (f"\n{b}" if b else ""))
            if ERROR.search(b):
                failed = cmd
                print("!!! error - sending abort")
                for _ in range(2):
                    await send(proc, "abort")
                break
        log.append("\n===== VERIFY =====")
        for v in VERIFY:
            b = body(await send(proc, v))
            log.append(f">>> {v}\n{b}")
            print(f">>> {v}\n{b}")
            if v.endswith("setting"):
                verified = all(s in b for s in ("set status enable", '"10.1.20.13"', "set port 514", '"10.4.20.254"'))
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_syslog-apply-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    ok = not failed and verified
    AuditLog(Settings.load().audit_abs).record(action="syslog.apply", target=NAME, transport="ssh",
                                               result="ok" if ok else "error",
                                               detail={"server": "10.1.20.13:514", "stopped_at": failed or "", "verified": verified})
    print(f"\nRESULT: {'OK' if ok else 'FAILED'}{' (stopped at: ' + failed + ')' if failed else ''}"
          f"{'' if verified else ' (read-back mismatch)'}\ntranscript: {path}")


asyncio.run(main())
