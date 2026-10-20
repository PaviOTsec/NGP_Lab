"""Point SCALANCE switches at the SINEC INS NTP server (DMZH1_SinecINS 10.1.20.21).

Per device, ONE AT A TIME, over SSH (host key pinned on the authenticating connection):
  read `show ntp info` + `show time`; if peer 10.1.20.21 and Mode NTP -> no change (read-only login)
  else: configure terminal -> ntp -> ntp server id 1 ipv4 10.1.20.21 -> ntp time diff +08:00
        -> exit -> time ntp -> end   (same sheet as tools/nms-onboarding/nms_apply_scalance.py)
Stops at the first error response. Reads back and checks the server is listed.
SCALANCE auto-saves every command.

usage: python -I scalance_ntp.py <backend_dir> <out_dir> <device | name=ip=ssh_fp> [...]
  name=ip=ssh_fp = a SCALANCE outside the inventory (rule-13 exception/override), pinned by host key.
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
DEVICES = sys.argv[3:]
assert DEVICES
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

SERVER = "10.1.20.21"  # DMZH1_SinecINS
COMMANDS = ["configure terminal", "ntp", f"ntp server id 1 ipv4 {SERVER}", "ntp time diff +08:00",
            "exit", "time ntp", "end"]
VERIFY = ["show ntp info", "show time"]  # NB `show ntp server info` = the switch's own NTP server, not the client


def configured(outs: dict[str, str]) -> bool:
    peer = re.search(rf"Peer IP Address\s*:\s*{re.escape(SERVER)}\b", outs.get("show ntp info", ""))
    mode = re.search(r"(?m)^\s*Mode\s*:\s*NTP\b", outs.get("show time", ""))
    return bool(peer and mode)

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
    log, failed, verified, changed = [], None, False, False
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        log.append("===== BEFORE =====")
        before: dict[str, str] = {}
        for v in VERIFY:
            before[v] = b = body(await send(proc, v))
            log.append(f">>> {v}\n{b}")
            print(f"{dev.name}: before: {v}\n{b}")
        if configured(before):
            print(f"{dev.name}: {SERVER} already configured; no change")
            verified = True
        else:
            changed = True
            log.append("\n===== CHANGE =====")
            for cmd in COMMANDS:
                b = body(await send(proc, cmd))
                log.append(f">>> {cmd}\n{b}")
                print(f"{dev.name}: >>> {cmd}" + (f"\n{b}" if b else ""))
                if ERROR.search(b):
                    failed = cmd
                    await send(proc, "end")
                    break
            log.append("\n===== VERIFY =====")
            after: dict[str, str] = {}
            for v in VERIFY:
                after[v] = b = body(await send(proc, v))
                log.append(f">>> {v}\n{b}")
                print(f"{dev.name}: {v}\n{b}")
            verified = configured(after)
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{dev.name}_{dev.address}_{time.strftime('%Y%m%d-%H%M%S')}_ntp-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    ok = not failed and verified
    audit.record(action="ntp.apply" if changed else "ntp.check", target=dev.name, transport="ssh",
                 result="ok" if ok else "error",
                 detail={"server": SERVER, "changed": changed, "stopped_at": failed or "", "verified": verified})
    print(f"{dev.name}: RESULT {'OK' if ok else 'FAILED'}{' (changed)' if changed else ' (unchanged)'}"
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
