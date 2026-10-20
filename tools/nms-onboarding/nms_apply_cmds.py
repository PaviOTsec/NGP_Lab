"""Phase 4/6: apply the reviewed SCALANCE command sheet (SNMPv3 user + NTP) to ONE device.

One command at a time; stops at the first error response. Transcript has secrets masked.
SSH host key pinned on the authenticating connection. Auto-save is on (each command persists).

usage: python -I nms_apply_scalance.py <backend_dir> <out_dir> <name> <ip> <ssh_fp> <sha256|sha>
"""
import asyncio
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
NAME, IP, FP = sys.argv[3:6]; AUTH = "sha"; EXTRA_CMDS = sys.argv[6].split(";;")
assert AUTH in ("sha256", "sha")
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"\*?CLI(\([\w-]+\))?#\s*$")
ERROR = re.compile(r"(?im)^\s*%|invalid|error|incomplete|not allowed|failed")

COMMANDS = EXTRA_CMDS
VERIFY = ["show snmp", "show running-config snmp",
          "show device information"]


async def send(proc, cmd: str, maxwait: float = 30.0) -> str:
    proc.stdin.write(cmd + "\n")
    buf, loop = "", asyncio.get_running_loop()
    end = loop.time() + maxwait
    while loop.time() < end:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(65536), timeout=3.0)
        except asyncio.TimeoutError:
            if PROMPT.search(ANSI.sub("", buf).rstrip()):
                break
            continue
        if not chunk:
            break
        buf += chunk
        if re.search(r"--\s*More\s*--", ANSI.sub("", buf[-200:])):
            proc.stdin.write(" ")
    return ANSI.sub("", buf).replace("\r", "")


async def main() -> None:
    settings = Settings.load()
    audit = AuditLog(settings.audit_abs)
    store = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    login = store.credential("network/admin")
    secrets = {"{AUTH}": store.credential("snmpv3/nms").password, "{PRIV}": store.credential("snmpv3/nms-priv").password}
    mask = lambda s: re.sub("|".join(re.escape(v) for v in secrets.values()), "********", s)  # noqa: E731

    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed = [], None
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        for tmpl in COMMANDS:
            cmd = tmpl
            for k, v in secrets.items():
                cmd = cmd.replace(k, v)
            out = await send(proc, cmd)
            body = out.split("\n", 1)[1] if "\n" in out else ""
            log.append(f">>> {mask(cmd)}\n{mask(body).strip()}")
            print(f">>> {mask(cmd)}")
            if ERROR.search(re.sub(r"(?m)^.*CLI.*#\s*$", "", body)):
                failed = mask(cmd)
                print(f"!!! error response â€” stopping:\n{mask(body).strip()}")
                await send(proc, "end")
                break
        log.append("\n===== VERIFY =====")
        for v in VERIFY:
            out = await send(proc, v)
            log.append(f">>> {v}\n{mask(out.split(chr(10), 1)[1] if chr(10) in out else out).strip()}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    ts = time.strftime("%Y%m%d-%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{ts}_cmds-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    audit.record(action="nms.apply-cmds", target=NAME, transport="ssh",
                 result="error" if failed else "ok", detail={"stopped_at": failed or ""})
    print(f"\nRESULT: {'STOPPED at: ' + failed if failed else 'all commands accepted'}\ntranscript: {path}")


asyncio.run(main())

