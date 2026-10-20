"""FW-South (PAN-OS 11.1): allow DMZ -> L2 + L1, any/any (operator 2026-10-19, rule-13 override).

  rule  DMZ-to-OT-Allow: LevelDmzZone -> Level2Zone, source any, destination any,
        application/service any, allow. log-start/log-end no (firewalls log deny only).
        Existing Internal-Cross-Subnet-NAT still applies (DMZ seen in OT as 192.168.20.189).
Candidate config: refuse if changes are pending -> set -> diff gate (additions only, expected keys) ->
commit. Any error/unexpected diff/--dry-run: `revert config` (nothing committed).
Rollback after commit: `delete rulebase security rules DMZ-to-OT-Allow` + commit, or
`load config from pre-dmz-ot-20261019.xml` + commit (snapshot on the box).
usage: python -I panos_dmz_ot.py <backend_dir> <out_dir> [--dry-run]"""
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
RULE = "set rulebase security rules DMZ-to-OT-Allow"
COMMANDS = [
    f"{RULE} from LevelDmzZone to Level2Zone source any destination any source-user any "
    "category any application any service any action allow log-start no log-end no",
    f'{RULE} description "DMZ to L2 + L1, any/any (operator 2026-10-19)"',
]
# every added line must be one of these keys (first token), or a closing brace
KEYS = {"DMZ-to-OT-Allow", "from", "to", "source", "destination", "source-user", "category", "application",
        "service", "action", "log-start", "log-end", "description", "}"}
VERIFY = [
    "show config diff",
    "test security-policy-match from LevelDmzZone to Level2Zone source 10.1.20.56 destination 192.168.4.10 protocol 6 destination-port 502",
    "test security-policy-match from LevelDmzZone to Level2Zone source 10.1.20.56 destination 192.168.4.10 protocol 1",
    "test security-policy-match from LevelDmzZone to Level2Zone source 10.1.20.56 destination 192.168.20.50 protocol 6 destination-port 8443",
    "test security-policy-match from LevelDmzZone to Level2Zone source 10.1.20.56 destination 192.168.1.15 protocol 6 destination-port 102",
    "test nat-policy-match from LevelDmzZone to Level2Zone source 10.1.20.56 destination 192.168.4.10 protocol 6 destination-port 502 to-interface ethernet1/6",
    "show running security-policy",
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
            res = await send(proc, 'commit description "DMZ to L2+L1 any/any (operator 2026-10-19)"', maxwait=600)
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
            if v.startswith("test"):
                print(f">>> {v}\n{out[:500]}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_dmz-ot-{'dryrun' if DRY else 'apply'}-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="fw.dmz-to-ot-allow", target=NAME, transport="ssh",
                                               result="committed" if committed else "reverted",
                                               detail={"reason": failed or "", "dry_run": DRY})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\ntranscript: {path}")


asyncio.run(main())
