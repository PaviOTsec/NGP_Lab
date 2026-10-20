"""Port mirroring (SPAN) on SCALANCE switches: every other GbE port (both directions) -> the LAST GbE port.

Per device, ONE AT A TIME, over SSH (host key pinned on the authenticating connection):
  read `show monitor`, `show monitor session 1`, `show interfaces status`
  destination = highest-numbered Gi0/N (SW-DMZ XC416-8: Gi0/16; XC208G: Gi0/8; Ex ports ignored)
  already mirroring Gi0/1..N-1 both -> Gi0/N and Active -> no change (read-only login)
  refuse (no change) if Gi0/N is connected or session 1 already has a different setup
  else: configure terminal -> monitor session 1 destination interface gigabitethernet 0/N
        -> monitor session 1 source interface gigabitethernet 0/i both (i = 1..N-1) -> monitor -> end
Stops at the first error response. Reads back `show monitor session 1`. SCALANCE auto-saves.
Rollback: configure terminal -> no monitor session 1 -> no monitor -> end.

usage: python -I scalance_span.py <backend_dir> <out_dir> <device | name=ip=ssh_fp> [...]
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

READ = ["show monitor", "show monitor session 1", "show interfaces status"]

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


def ports(status: str) -> dict[int, str]:
    """Gi0/n -> 'connected' / 'not connected' from `show interfaces status`."""
    return {int(n): s for n, s in re.findall(r"(?m)^Gi0/(\d+)\s+(connected|not connected)\b", status)}


def session(out: str) -> tuple[list[int], list[int], str]:
    """(both-direction source ports, destination ports, status) from `show monitor session 1`."""
    both = re.search(r"(?s)Both\s*:\s*(.*?)(?:\n\s*\w[\w ]*:|\Z)", out)
    dest = re.search(r"Destination Ports?\s*:\s*([^\n]*)", out)
    stat = re.search(r"Status\s*:\s*(\w+)", out)
    gi = lambda m: sorted(int(n) for n in re.findall(r"Gi0/(\d+)", m.group(1))) if m else []  # noqa: E731
    return gi(both), gi(dest), stat.group(1) if stat else ""


def wanted(outs: dict[str, str], last: int) -> bool:
    src, dst, stat = session(outs.get("show monitor session 1", ""))
    return src == list(range(1, last)) and dst == [last] and stat.lower() == "active"


async def one(dev, cred, audit: AuditLog) -> bool:
    key = await asyncssh.get_server_host_key(dev.address, 22)
    if key.get_fingerprint() != dev.ssh_fingerprint:
        print(f"{dev.name}: host key mismatch; no credentials sent")
        return False
    conn = await asyncssh.connect(dev.address, username=cred.username, password=cred.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed, refused, verified, changed, last = [], None, "", False, False, 0
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        log.append("===== BEFORE =====")
        before: dict[str, str] = {}
        for v in READ:
            before[v] = b = body(await send(proc, v))
            log.append(f">>> {v}\n{b}")
            print(f"{dev.name}: before: {v}\n{b}")
        link = ports(before["show interfaces status"])
        last = max(link) if link else 0
        src, dst, _ = session(before["show monitor session 1"])
        if not last:
            refused = "could not read the port list"
        elif wanted(before, last):
            print(f"{dev.name}: already mirroring Gi0/1-{last - 1} -> Gi0/{last}; no change")
            verified = True
        elif link[last] == "connected":
            refused = f"destination Gi0/{last} is connected (it would stop forwarding)"
        elif src or dst:
            refused = f"session 1 already exists (sources {src}, destination {dst})"
        else:
            changed = True
            cmds = (["configure terminal", f"monitor session 1 destination interface gigabitethernet 0/{last}"]
                    + [f"monitor session 1 source interface gigabitethernet 0/{i} both" for i in range(1, last)]
                    + ["monitor", "end"])
            log.append("\n===== CHANGE =====")
            for cmd in cmds:
                b = body(await send(proc, cmd))
                log.append(f">>> {cmd}\n{b}")
                print(f"{dev.name}: >>> {cmd}" + (f"\n{b}" if b else ""))
                if ERROR.search(b):
                    failed = cmd
                    await send(proc, "end")
                    break
            log.append("\n===== VERIFY =====")
            after: dict[str, str] = {}
            for v in READ[:2]:
                after[v] = b = body(await send(proc, v))
                log.append(f">>> {v}\n{b}")
                print(f"{dev.name}: {v}\n{b}")
            verified = wanted(after, last)
        if refused:
            log.append(f"\nREFUSED: {refused}")
            print(f"{dev.name}: REFUSED: {refused}; nothing changed")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{dev.name}_{dev.address}_{time.strftime('%Y%m%d-%H%M%S')}_span-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    ok = not failed and not refused and verified
    audit.record(action="mirroring.apply" if changed else "mirroring.check", target=dev.name, transport="ssh",
                 result="ok" if ok else "error",
                 detail={"destination": f"Gi0/{last}", "sources": f"Gi0/1-{last - 1} both", "changed": changed,
                         "stopped_at": failed or "", "refused": refused, "verified": verified})
    print(f"{dev.name}: RESULT {'OK' if ok else 'FAILED'}{' (changed)' if changed else ' (unchanged)'}"
          f"{' (stopped at: ' + failed + ')' if failed else ''}{'' if verified or refused else ' (read-back mismatch)'}"
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
