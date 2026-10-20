"""Point SCALANCE switches at the Scribbler syslog server (DMZH1_LogServer) — or undo it.

Per device, ONE AT A TIME, over SSH (host key pinned on the authenticating connection):
  apply : events -> syslogserver ipv4 <server> <port> -> client config syslog
  remove: events -> no client config syslog -> no syslogserver ipv4 <server>
Stops at the first error response. Reads back `show events syslogserver` / `show events config`
and checks the server is (or is no longer) listed. SCALANCE auto-saves every command.
Event-to-syslog mappings (`event config ... syslog`) are factory defaults and left as they are.

usage: python -I scalance_syslog.py <backend_dir> <out_dir> apply|remove <device | name=ip=ssh_fp> [...]
  name=ip=ssh_fp = a SCALANCE outside the inventory (rule-13 exception), pinned by host key.
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
MODE = sys.argv[3]
DEVICES = sys.argv[4:]
assert MODE in ("apply", "remove") and DEVICES
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

SERVER, PORT = "10.1.20.13", 514  # DMZH1_LogServer, Scribbler Logstash UDP input
COMMANDS = {
    "apply": ["configure terminal", "events", f"syslogserver ipv4 {SERVER} {PORT}", "client config syslog", "end"],
    "remove": ["configure terminal", "events", "no client config syslog", f"no syslogserver ipv4 {SERVER}", "end"],
}
VERIFY = ["show events syslogserver", "show events config", "show events severity"]

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"\*?CLI(\([\w-]+\))?#\s*$")
ERROR = re.compile(r"(?im)^\s*%|invalid|error|incomplete|not allowed|failed")


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


def body(out: str) -> str:
    return re.sub(r"(?m)^.*CLI.*#\s*$", "", out.split("\n", 1)[1] if "\n" in out else "").strip()


async def one(dev, cred, audit: AuditLog) -> bool:
    key = await asyncssh.get_server_host_key(dev.address, 22)
    if key.get_fingerprint() != dev.ssh_fingerprint:
        print(f"{dev.name}: host key mismatch; no credentials sent")
        return False
    conn = await asyncssh.connect(dev.address, username=cred.username, password=cred.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed, verified = [], None, False
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        for cmd in COMMANDS[MODE]:
            b = body(await send(proc, cmd))
            log.append(f">>> {cmd}\n{b}")
            print(f"{dev.name}: >>> {cmd}" + (f"\n{b}" if b else ""))
            if ERROR.search(b):
                failed = cmd
                await send(proc, "end")
                break
        log.append("\n===== VERIFY =====")
        for v in VERIFY:
            b = body(await send(proc, v))
            log.append(f">>> {v}\n{b}")
            if v == "show events syslogserver":
                listed = SERVER in b
                verified = listed if MODE == "apply" else not listed
                print(f"{dev.name}: {v}\n{b}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{dev.name}_{dev.address}_{time.strftime('%Y%m%d-%H%M%S')}_syslog-{MODE}-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    ok = not failed and verified
    audit.record(action=f"syslog.{MODE}", target=dev.name, transport="ssh", result="ok" if ok else "error",
                 detail={"server": f"{SERVER}:{PORT}", "stopped_at": failed or "", "verified": verified})
    print(f"{dev.name}: RESULT {'OK' if ok else 'FAILED'}"
          f"{' (stopped at: ' + failed + ')' if failed else ''}{'' if verified else ' (read-back mismatch)'}"
          f"\n{dev.name}: transcript {path}\n")
    return ok


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    audit = AuditLog(settings.audit_abs)
    by_name = {t.name: t for t in inv.all() if t.kind == "network" and t.vendor == "scalance"}
    for arg in DEVICES:  # sequential: stop the rollout at the first failure
        if "=" in arg:  # off-inventory device: same credential, host key pin given explicitly
            name, ip, fp = arg.split("=", 2)
            by_name[name] = SimpleNamespace(name=name, address=ip, ssh_fingerprint=fp, credential="network/admin")
        else:
            name = arg
        dev = by_name.get(name)
        if dev is None:
            sys.exit(f"{name}: not a SCALANCE device in the inventory")
        if not await one(dev, creds.credential(dev.credential), audit):
            sys.exit(f"stopped after {name}")


asyncio.run(main())
