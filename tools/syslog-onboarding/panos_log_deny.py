"""FW-South (PAN-OS 11.1): log only denied traffic (operator 2026-10-19).

  every security rule with action allow (read live from `show running security-policy`):
        log-start no, log-end no
  log-forwarding profile Scribbler-Deny: traffic logs ("All Logs") -> syslog profile Scribbler
  interzone-default (deny): log-end yes, log-setting Scribbler-Deny  (intrazone-default stays unlogged)
Candidate config: refuse if pending -> set -> diff gate -> commit. The gate allows only the log lines,
the new profile and the default-rule override. Error/unexpected diff/--dry-run: `revert config`.
Rollback: `load config from pre-logging-20261019.xml` + commit.
usage: python -I panos_log_deny.py <backend_dir> <out_dir> [--dry-run]"""
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
TAIL = [
    'set shared log-settings profiles Scribbler-Deny match-list Deny-Traffic log-type traffic filter "All Logs" send-syslog Scribbler',
    "set rulebase default-security-rules rules interzone-default action deny log-end yes log-setting Scribbler-Deny",
]
ADD_KEYS = {"log-start", "log-end", "log-settings", "profiles", "Scribbler-Deny", "match-list", "Deny-Traffic",
            "log-type", "filter", "send-syslog", "default-security-rules", "rules", "interzone-default", "action",
            "log-setting", "}"}
DEL_OK = re.compile(r"^\s*-\s*log-(end yes|start (yes|no));\s*$")
VERIFY = ["show config diff", "show running security-policy",
          "show config running xpath devices/entry/vsys/entry/rulebase/default-security-rules",
          "show config running xpath shared/log-settings/profiles"]


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


def allow_rules(policy: str) -> tuple[list[str], list[str]]:
    rules = [(n, b) for n, b in re.findall(r'(?s)"([^";]+); index: \d+" \{(.*?)\n\}', policy)
             if n not in ("intrazone-default", "interzone-default")]  # built-in; handled via default-security-rules
    allow = [n for n, b in rules if re.search(r"(?m)^\s*action allow;", b)]
    return allow, [n for n, _ in rules if n not in allow]


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
        allow, other = allow_rules(await send(proc, "show running security-policy"))
        print(f"allow rules ({len(allow)}): {', '.join(allow)}\nnon-allow rules (logging kept): {other or 'none'}")
        log.append(f"allow rules: {allow}\nnon-allow rules: {other}")
        if not allow:
            sys.exit("no allow rules parsed - not touching")
        await send(proc, "configure")
        for cmd in [f"set rulebase security rules {n} log-start no log-end no" for n in allow] + TAIL:
            out = await send(proc, cmd)
            log.append(f">>> {cmd}\n{out.strip()}")
            if ERROR.search(out):
                failed = cmd
                print(f"!!! error on: {cmd}\n{out.strip()[:300]}")
                break
        diff = await send(proc, "run show config diff") if not failed else ""
        log.append(">>> run show config diff\n" + diff.strip())
        changed = [ln for ln in diff.splitlines() if re.match(r"^\s*[+-]", ln)]
        bad = [ln for ln in changed if (ln.lstrip().startswith("-") and not DEL_OK.match(ln))
               or (ln.lstrip().startswith("+") and re.split(r"[\s;{]+", ln.lstrip("+ ").strip())[0] not in ADD_KEYS)]
        print(f"diff: {len(changed)} changed lines; unexpected: {bad[:5]}")
        print("\n".join(ln for ln in changed if "log-end" not in ln and "log-start" not in ln))
        if failed or not changed or bad or DRY:
            reason = failed or ("dry-run" if DRY else "unexpected/empty diff")
            print("REVERT:", reason)
            log.append(">>> revert config\n" + (await send(proc, "revert config")).strip())
            failed = failed or reason
        else:
            res = await send(proc, 'commit description "Log only denied traffic; deny logs to Scribbler (operator 2026-10-19)"',
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
            if committed and v == "show running security-policy":
                still = [n for n, b in re.findall(r'(?s)"([^";]+); index: \d+" \{(.*?)\n\}', out)
                         if n in allow and re.search(r"log-(end|start) yes", b)]
                print("allow rules still logging after commit:", still or "none")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_log-deny-{'dryrun' if DRY else 'apply'}-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="fw.log-deny-only", target=NAME, transport="ssh",
                                               result="committed" if committed else "reverted",
                                               detail={"reason": failed or "", "dry_run": DRY, "allow_rules": len(allow)})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\ntranscript: {path}")


asyncio.run(main())
