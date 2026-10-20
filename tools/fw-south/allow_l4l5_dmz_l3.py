"""FW-South (PAN-OS 11.1): allow L4/L5 <-> DMZ/L3 on ANY port (setup phase, operator 2026-10-16).

Why: Allow_NorthFirewall_Incoming/_Outgoing use `service application-default`, so App-ID resets
anything on a non-standard port (Splunk 8089/8000/9997, SSM 8443, WinRM 5985 from MC01 ...).
Adds two rules ABOVE those (existing rules are not modified):
  L4L5-to-DMZ-L3-AnyPort  TransitZone -> LevelDmzZone/Level3Zone, 10.4.20/24+10.5.20/24 -> 10.1.20/24+192.168.30/24
  DMZ-L3-to-L4L5-AnyPort  the reverse
application any, service any, allow, log-end. No L2 zone or subnet is involved (CLAUDE.md rule 13).

Pinned host key -> refuse if the candidate already has changes -> `save config to <snapshot>` +
rulebase text into the transcript -> set + move -> diff gate (only '+' lines, both rule names) ->
commit; on any error / unexpected diff / --dry-run: `revert config` (nothing committed).
Rollback after commit: --remove (deletes the two rules, same gate, commit).
usage: python -I -X utf8 tools/fw-south/allow_l4l5_dmz_l3.py <backend_dir> <out_dir> [--dry-run] [--remove]
"""
import asyncio
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
DRY, REMOVE = "--dry-run" in sys.argv, "--remove" in sys.argv
NAME, IP, FP = "FW-South", "10.1.20.254", "SHA256:2ti0+ABa6tURBaXu5K/og/4q7H2w2TUyluKOndZj7GQ"
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROMPT = re.compile(r"admin@PA-[\w-]+[>#]\s*$")
ERROR = re.compile(r"(?i)invalid syntax|server error|unknown command|validation error|failed|is not a valid|error:")
STAMP = time.strftime("%Y%m%d-%H%M%S")
SNAPSHOT = f"l4dmz-{STAMP}.xml"  # PAN-OS: snapshot names <= 32 chars
R_IN, R_OUT = "L4L5-to-DMZ-L3-AnyPort", "DMZ-L3-to-L4L5-AnyPort"
NORTH, SOUTH = "[ 10.4.20.0/24 10.5.20.0/24 ]", "[ 10.1.20.0/24 192.168.30.0/24 ]"
DESC = '"Operator 2026-10-16 setup phase: any port L4/L5<->DMZ/L3 (application-default blocked 8089/8443/8000/5985)"'
RULE = ("set rulebase security rules {n} from {f} to {t} source {s} destination {d} source-user any "
        "category any application any service any action allow log-end yes description " + DESC)
ADD = [
    RULE.format(n=R_IN, f="TransitZone", t="[ LevelDmzZone Level3Zone ]", s=NORTH, d=SOUTH),
    f"move rulebase security rules {R_IN} before Allow_NorthFirewall_Incoming",
    RULE.format(n=R_OUT, f="[ LevelDmzZone Level3Zone ]", t="TransitZone", s=SOUTH, d=NORTH),
    f"move rulebase security rules {R_OUT} before Allow_NorthFirewall_Outgoing",
]
DEL = [f"delete rulebase security rules {R_IN}", f"delete rulebase security rules {R_OUT}"]
RULEBASE = "show config running xpath devices/entry/vsys/entry/rulebase/security"


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
    commands = DEL if REMOVE else ADD
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(400, 60))
        await send(proc, "")
        await send(proc, "set cli pager off")
        pend = await send(proc, "show config diff")
        log.append(">>> show config diff (before)\n" + pend.strip())
        if re.search(r"(?m)^\s*[+-]\s*\S", pend) or ERROR.search(pend):
            sys.exit("candidate already has pending changes - not touching")
        log.append(f">>> {RULEBASE} (before)\n" + (await send(proc, RULEBASE)).strip())
        await send(proc, "configure")
        snap = await send(proc, f"save config to {SNAPSHOT}")
        log.append(f">>> save config to {SNAPSHOT}\n{snap.strip()}")
        print(f"snapshot: {SNAPSHOT}: {' '.join(snap.split())[:120]}")
        if not re.search(r"(?i)saved|success", snap):
            failed = "snapshot not confirmed"
        for cmd in ([] if failed else commands):
            out = await send(proc, cmd)
            log.append(f">>> {cmd}\n{out.strip()}")
            print(f">>> {cmd}")
            if ERROR.search(out):
                failed = cmd; print("!!! error:", out.strip()[:300]); break
        diff = await send(proc, "run show config diff") if not failed else ""
        log.append(">>> run show config diff\n" + diff.strip())
        changed = [ln for ln in diff.splitlines() if re.match(r"^\s*[+-]", ln)]
        sign = "-" if REMOVE else "+"
        bad = [ln for ln in changed if not ln.lstrip().startswith(sign)]
        names_ok = R_IN in diff and R_OUT in diff
        print(f"diff: {len(changed)} changed lines | unexpected: {bad[:5]} | both rules in diff: {names_ok}")
        print("\n".join(changed[:60]))
        if failed or not changed or bad or not names_ok or DRY:
            reason = failed or ("dry-run" if DRY else "unexpected/empty diff")
            print("REVERT:", reason)
            log.append(">>> revert config\n" + (await send(proc, "revert config")).strip())
            failed = failed or reason
        else:
            what = "remove" if REMOVE else "add"
            res = await send(proc, f'commit description "{what} L4/L5<->DMZ/L3 any-port rules (setup phase)"', maxwait=600)
            log.append(">>> commit\n" + res.strip())
            print("commit:", " ".join(res.split())[:300])
            committed = bool(re.search(r"(?i)committed successfully|commit job .* (complete|succeeded)", res))
            job = re.search(r"(?i)commit job (\d+) is in progress", res)
            if not committed and job:
                # Queued commit: PAN refuses `revert config` while it runs, so wait for the job.
                # (2026-10-16 job 90 was misread as failed here, though it committed fine.)
                for _ in range(60):
                    await asyncio.sleep(10)
                    st = await send(proc, f"run show jobs id {job.group(1)}")
                    if re.search(r"\bFIN\b", st):
                        log.append(f">>> run show jobs id {job.group(1)}\n{st.strip()}")
                        committed = bool(re.search(r"\bFIN\s+OK\b|committed successfully", st))
                        break
                print(f"commit job {job.group(1)}: {'OK' if committed else 'not OK / not finished'}")
            if not committed:
                failed = "commit did not report success"
                log.append(">>> revert config (after failed commit)\n" + (await send(proc, "revert config")).strip())
                print("commit failed -> candidate reverted")
        await send(proc, "exit")
        log.append("\n===== VERIFY =====")
        for v in ("show config diff", RULEBASE):
            log.append(f">>> {v}\n{(await send(proc, v)).strip()}")
        proc.stdin.write("exit\n"); await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{STAMP}_{'remove' if REMOVE else 'apply'}-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(
        action="fw-south.l4l5-dmz-anyport." + ("remove" if REMOVE else "add"), target=NAME, transport="ssh",
        result="committed" if committed else "reverted", detail={"reason": failed or "", "snapshot": SNAPSHOT})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\n"
          f"snapshot on box: {SNAPSHOT}\ntranscript: {path}")


asyncio.run(main())
