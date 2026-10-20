"""FW-North (FortiOS 7.4): log only denied traffic (operator 2026-10-19).

  firewall policies read live: action accept -> logtraffic disable; anything else (deny) -> logtraffic all
  log setting: fwpolicy-implicit-log enable (implicit deny), local-in-deny-unicast enable,
               local-out disable (the firewall's own allowed sessions)
The syslogd filter (forward-traffic/local-traffic enable) then forwards only these deny logs.
Line by line; first error -> `abort` and stop. Rollback: restore Backups/20261019-fw-logging/FW-North
config.txt (System > Configuration > Restore), or re-set logtraffic all / the three log settings.
usage: python -I fortigate_log_deny.py <backend_dir> <out_dir>"""
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
LOG_SETTING = ["config log setting", "set fwpolicy-implicit-log enable", "set local-in-deny-unicast enable",
               "set local-out disable", "end"]


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


def policies(show: str) -> dict[str, dict[str, str]]:
    """edit-id -> {action, logtraffic} from `show full-configuration firewall policy`."""
    res = {}
    for pid, blk in re.findall(r"(?s)^\s{4}edit (\d+)\n(.*?)^\s{4}next", show, re.M):
        act = re.search(r"set action (\w+)", blk)
        lt = re.search(r"set logtraffic (\w+)", blk)
        res[pid] = {"action": act.group(1) if act else "deny", "logtraffic": lt.group(1) if lt else "?"}
    return res


async def main():
    login = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=login.username, password=login.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    log, failed = [], None
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await send(proc, "")
        before = policies(body(await send(proc, "show full-configuration firewall policy", maxwait=90)))
        log.append(f">>> policies before: {before}")
        print("before:", before)
        if not before:
            sys.exit("no policies parsed - not touching")
        cmds = ["config firewall policy"]
        for pid, p in before.items():
            cmds += [f"edit {pid}", f"set logtraffic {'disable' if p['action'] == 'accept' else 'all'}", "next"]
        cmds += ["end"] + LOG_SETTING
        for cmd in cmds:
            b = body(await send(proc, cmd))
            log.append(f">>> {cmd}\n{b}")
            if ERROR.search(b):
                failed = cmd
                print(f"!!! error on: {cmd}\n{b}\n-> abort")
                for _ in range(2):
                    await send(proc, "abort")
                break
        after = policies(body(await send(proc, "show full-configuration firewall policy", maxwait=90)))
        ls = body(await send(proc, "show full-configuration log setting"))
        log.append(f"\n===== VERIFY =====\npolicies after: {after}\n>>> log setting\n{ls}")
        print("after:", after)
        print("\n".join(ln.strip() for ln in ls.splitlines() if re.search(r"implicit-log|local-in-deny|local-out ", ln)))
        wrong = [pid for pid, p in after.items()
                 if p["logtraffic"] != ("disable" if p["action"] == "accept" else "all")]
        ok_ls = all(s in ls for s in ("set fwpolicy-implicit-log enable", "set local-in-deny-unicast enable",
                                       "set local-out disable"))
        if wrong or not ok_ls:
            failed = failed or f"read-back mismatch (policies {wrong}, log setting ok={ok_ls})"
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_log-deny-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="fw.log-deny-only", target=NAME, transport="ssh",
                                               result="error" if failed else "ok", detail={"reason": failed or ""})
    print(f"\nRESULT: {'FAILED: ' + failed if failed else 'OK'}\ntranscript: {path}")


asyncio.run(main())
