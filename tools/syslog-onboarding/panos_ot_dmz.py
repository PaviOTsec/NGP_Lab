"""FW-South (PAN-OS 11.1): allow OT -> DMZ, any service (operator 2026-10-19, rule-13 override).

  rule  OT-to-DMZ-Allow: Level2Zone -> LevelDmzZone, src 192.168.1-4.0/24 + 192.168.20.0/24,
        dst 10.1.20.0/24, application/service any, allow, log-end. No NAT (sources stay visible).
  route Return_to_Level1_Net4: 192.168.4.0/24 via 192.168.20.254 on ethernet1/6
        (192.168.0.0/22 is already routed by Return_to_Level1).
Candidate config: refuse if changes are pending -> set -> diff gate (additions only, expected keys) ->
commit. Any error/unexpected diff/--dry-run: `revert config` (nothing committed).
Rollback after commit: `load config from pre-ot-dmz-20261019.xml` + commit (snapshot on the box), or
delete the two nodes and commit.
usage: python -I panos_ot_dmz.py <backend_dir> <out_dir> [--dry-run]"""
import asyncio
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
DRY = "--dry-run" in sys.argv
NAME, IP, FP = "FW-South", "10.1.20.254", "SHA256:2ti0+ABa6tURBaXu5K/og/4q7H2w2TUyluKOndZj7GQ"
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"admin@PA-[\w-]+[>#]\s*$")
ERROR = re.compile(r"(?i)invalid syntax|server error|unknown command|validation error|failed|is not a valid|error:")
OT_SRC = "[ 192.168.1.0/24 192.168.2.0/24 192.168.3.0/24 192.168.4.0/24 192.168.20.0/24 ]"
RULE = "set rulebase security rules OT-to-DMZ-Allow"
COMMANDS = [
    f"{RULE} from Level2Zone to LevelDmzZone source {OT_SRC} destination 10.1.20.0/24 source-user any "
    "category any application any service any action allow log-end yes",
    f'{RULE} description "OT L1 192.168.1-4.0/24 + L2 192.168.20.0/24 to DMZ, any service (operator 2026-10-19)"',
    "set network virtual-router default routing-table ip static-route Return_to_Level1_Net4 "
    "destination 192.168.4.0/24 interface ethernet1/6 metric 10 nexthop ip-address 192.168.20.254",  # nexthop last
]
# every added line must be one of these keys (first token), or a closing brace
KEYS = {"OT-to-DMZ-Allow", "from", "to", "source", "destination", "source-user", "category", "application",
        "service", "action", "log-end", "description", "Return_to_Level1_Net4", "nexthop", "ip-address",
        "interface", "metric", "}"}
VERIFY = [
    "show config diff",
    "test security-policy-match from Level2Zone to LevelDmzZone source 192.168.1.30 destination 10.1.20.13 protocol 17 destination-port 514",
    "test security-policy-match from Level2Zone to LevelDmzZone source 192.168.4.10 destination 10.1.20.17 protocol 6 destination-port 445",
    "test nat-policy-match from Level2Zone to LevelDmzZone source 192.168.1.30 destination 10.1.20.13 protocol 17 destination-port 514",
    "show routing route destination 192.168.4.0/24",
    "show running security-policy | match OT-to-DMZ-Allow",
]


async def send(proc, cmd, maxwait=120.0):
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
    t = ANSI.sub("", buf).replace("\r", "")
    return re.sub(r"(?s)^.*?" + re.escape(cmd[-40:]) + r"\n", "", t, count=1)  # drop PAN's typing redraw


async def main():
    login = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed, committed = [], None, False
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(400, 60))
        await send(proc, "")
        await send(proc, "set cli pager off")
        pend = await send(proc, "show config diff")
        log.append(">>> show config diff (before)\n" + pend.strip())
        if re.search(r"(?m)^\s*[+-]\s*\S", pend) or ERROR.search(pend):
            sys.exit("candidate already has pending changes - not touching")
        await send(proc, "configure")
        for cmd in COMMANDS:
            out = await send(proc, cmd)
            log.append(f">>> {cmd}\n{out.strip()}")
            print(f">>> {cmd}")
            if ERROR.search(out):
                failed = cmd
                print("!!! error:", out.strip()[:300])
                break
        diff = await send(proc, "run show config diff") if not failed else ""
        log.append(">>> run show config diff\n" + diff.strip())
        changed = [ln for ln in diff.splitlines() if re.match(r"^\s*[+-]", ln)]
        bad = [ln for ln in changed if ln.lstrip().startswith("-")
               or re.split(r"[\s;{]+", ln.lstrip("+ ").strip())[0] not in KEYS]
        print("diff:\n" + "\n".join(changed))
        print("unexpected:", bad[:5])
        if failed or not changed or bad or DRY:
            reason = failed or ("dry-run" if DRY else "unexpected/empty diff")
            print("REVERT:", reason)
            log.append(">>> revert config\n" + (await send(proc, "revert config")).strip())
            failed = failed or reason
        else:
            res = await send(proc, 'commit description "OT to DMZ allow + 192.168.4.0/24 route (operator 2026-10-19)"',
                             maxwait=600)
            log.append(">>> commit\n" + res.strip())
            print("commit:", " ".join(res.split())[:300])
            committed = bool(re.search(r"(?i)committed successfully|commit job .* (complete|succeeded)", res))
            if not committed:
                failed = "commit did not report success"
                log.append(">>> revert config (after failed commit)\n" + (await send(proc, "revert config")).strip())
                print("commit failed -> candidate reverted")
        await send(proc, "exit")
        log.append("\n===== VERIFY =====")
        for v in VERIFY:
            out = (await send(proc, v)).strip()
            log.append(f">>> {v}\n{out}")
            if v.startswith(("test", "show routing")):
                print(f">>> {v}\n{out[:700]}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_ot-dmz-{'dryrun' if DRY else 'apply'}-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="fw.ot-to-dmz-allow", target=NAME, transport="ssh",
                                               result="committed" if committed else "reverted",
                                               detail={"reason": failed or "", "dry_run": DRY})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\ntranscript: {path}")


asyncio.run(main())
