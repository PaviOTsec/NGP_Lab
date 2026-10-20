"""FW-North (FortiOS 7.4): clear forward sessions of the given firewall policies (and protocol), so that
sessions created before a logging change pick up the new per-policy log flag. Runtime state only — no
config change. Local-in sessions (e.g. this SSH login) are not matched by a policy filter.
UDP flows are simply re-created by the next packet; cleared TCP connections drop and must reconnect.
<since> = local time of the change, used as `filter duration` (NOTE: on FortiOS 7.4 this did not match
7-day-old sessions — its semantics are not session age), or `none` for no age filter (fine for UDP/ICMP,
which the next packet re-creates).
usage: python -I fortigate_clear_sessions.py <backend_dir> <out_dir> <since YYYY-mm-ddTHH:MM:SS|none>
       <proto:17|1|6|all> <policy-id> ..."""
import asyncio
import datetime as dt
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
SINCE = None if sys.argv[3] == "none" else dt.datetime.fromisoformat(sys.argv[3])
PROTO = sys.argv[4]
POLICIES = sys.argv[5:]
assert PROTO in ("17", "1", "6", "all") and POLICIES and all(p.isdigit() for p in POLICIES)
NAME, IP, FP = "FW-North", "10.4.20.254", "SHA256:38yWadbTq3bsXJFjMcoZJXDW1lafIZba2ZdYNNiamek"
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"FortiGate[\w-]*( \([\w-]+\))? [#$]\s*$")


async def send(proc, cmd, maxwait=60.0):
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


async def count(proc, pid: str) -> int:
    """Set the filter (policy, proto, older than SINCE) and return the matching session count."""
    await send(proc, "diagnose sys session filter clear")
    await send(proc, f"diagnose sys session filter policy {pid}")
    if PROTO != "all":
        await send(proc, f"diagnose sys session filter proto {PROTO}")
    if SINCE is not None:
        older = int((dt.datetime.now() - SINCE).total_seconds()) + 5  # +5 s margin: only pre-change sessions
        await send(proc, f"diagnose sys session filter duration {older}")
    m = re.search(r"total session:? (\d+)", await send(proc, "diagnose sys session list", maxwait=90))
    return int(m.group(1)) if m else -1


async def main():
    login = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, result = [], {}
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        for pid in POLICIES:
            before = await count(proc, pid)  # leaves the filter set for this policy/proto
            if before > 0:
                log.append(f">>> policy {pid} proto {PROTO}: clear\n{(await send(proc, 'diagnose sys session clear')).strip()}")
            after = await count(proc, pid)
            result[pid] = (before, after)
            print(f"policy {pid:>2} proto {PROTO}: sessions before={before} after={after}")
        await send(proc, "diagnose sys session filter clear")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_clear-sessions-proto{PROTO}.txt"
    path.write_text("\n".join(log + [f"{k}: before/after {v}" for k, v in result.items()]) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="fw.clear-sessions", target=NAME, transport="ssh", result="ok",
                                               detail={"proto": PROTO, "policies": result})
    print(f"transcript: {path}")


asyncio.run(main())
