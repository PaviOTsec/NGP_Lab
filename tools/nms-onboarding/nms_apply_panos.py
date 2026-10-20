"""Phase 6: FW-South (PAN-OS 11.1) â€” SNMPv3 user+view, SNMP on mgmt profile Allow-Ping-Mgmt,
NTP 10.1.20.21 + NTP service route via ethernet1/4. Candidate config: set -> diff gate -> commit.
On any error or unexpected diff: `revert config` (candidate discarded, nothing committed).
usage: python -I nms_apply_panos.py <backend_dir> <out_dir> [--dry-run]"""
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
V3 = "set deviceconfig system snmp-setting access-setting version v3"
COMMANDS = [
    f"{V3} views NMSView view all oid 1.3.6.1 option include mask 0xf0",
    f"{V3} users sinecnms view NMSView authproto SHA-256 authpwd {{AUTH}} privproto AES privpwd {{PRIV}}",
    "set network profiles interface-management-profile Allow-Ping-Mgmt snmp yes",
    "set deviceconfig system ntp-servers primary-ntp-server ntp-server-address 10.1.20.21",
    "set deviceconfig system ntp-servers primary-ntp-server authentication-type none",
    "set deviceconfig system route service ntp source interface ethernet1/4 address 10.1.20.254/24",
]
ALLOWED_DIFF = re.compile(r"snmp|NMSView|sinecnms|authpwd|privpwd|authproto|privproto|view|oid|option|mask|ntp|10\.1\.20\.21|"
                          r"authentication-type|none|route|service|source|interface|ethernet1/4|Allow-Ping-Mgmt|access-setting|version|v3|users|views|all|include|0xf0|1\.3\.6\.1|[{}]|^\s*$|yes;|AES|SHA-256|deviceconfig|system|network|profiles|interface-management-profile|setting|ntp-servers|primary-ntp-server|ntp-server-address", re.I)


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
    store = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    login = store.credential("network/admin")
    sec = {"{AUTH}": store.credential("snmpv3/nms").password, "{PRIV}": store.credential("snmpv3/nms-priv").password}
    mask = lambda s: re.sub("|".join(re.escape(v) for v in sec.values()), "********", s)  # noqa: E731
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
            sys.exit("candidate already has pending changes â€” not touching")
        await send(proc, "configure")
        for tmpl in COMMANDS:
            cmd = tmpl
            for k, v in sec.items():
                cmd = cmd.replace(k, v)
            out = await send(proc, cmd)
            log.append(f">>> {mask(cmd)}\n{mask(out).strip()}")
            print(f">>> {mask(cmd)}")
            if ERROR.search(out):
                failed = mask(cmd); print("!!! error:", mask(out).strip()[:300]); break
        diff = await send(proc, "run show config diff") if not failed else ""
        log.append(">>> run show config diff\n" + mask(diff).strip())
        changed = [ln for ln in diff.splitlines() if re.match(r"^\s*[+-]", ln)]
        KEYS = {"snmp", "snmp-setting", "access-setting", "version", "v3", "views", "NMSView", "view", "all", "oid", "option", "mask", "users", "sinecnms", "authproto", "authpwd", "privproto", "privpwd", "ntp-servers", "primary-ntp-server", "ntp-server-address", "authentication-type", "none", "route", "service", "ntp", "source", "interface", "address", "}"}
        bad = [ln for ln in changed if ln.lstrip().startswith("-") or re.split(r"[\s;{]+", ln.lstrip("+ ").strip())[0] not in KEYS]
        print("diff changed lines:", len(changed), "| unexpected:", bad[:5])
        if failed or not changed or bad or DRY:
            reason = failed or ("dry-run" if DRY else "unexpected/empty diff")
            print("REVERT:", reason)
            log.append(">>> revert config\n" + (await send(proc, "revert config")).strip())
            failed = failed or reason
        else:
            res = await send(proc, 'commit description "SINEC NMS onboarding: SNMPv3 + NTP"', maxwait=600)
            log.append(">>> commit\n" + res.strip())
            print("commit:", " ".join(res.split())[:300])
            committed = bool(re.search(r"(?i)committed successfully|commit job .* (complete|succeeded)", res))
            if not committed:
                failed = "commit did not report success"
                log.append(">>> revert config (after failed commit)\n" + (await send(proc, "revert config")).strip())
                print("commit failed -> candidate reverted")
                log.append(">>> revert config (after failed commit)\n" + (await send(proc, "revert config")).strip())
                print("commit failed -> candidate reverted")
        await send(proc, "exit")
        log.append("\n===== VERIFY =====")
        for v in ("show config diff", "show ntp",
                  "show config running xpath devices/entry/deviceconfig/system/snmp-setting",
                  "show config running xpath devices/entry/network/profiles/interface-management-profile",
                  "show config running xpath devices/entry/deviceconfig/system/route", "show clock"):
            log.append(f">>> {v}\n{mask(await send(proc, v)).strip()}")
        proc.stdin.write("exit\n"); await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_apply-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="nms-phase6.apply-panos", target=NAME, transport="ssh",
                                               result="committed" if committed else "reverted", detail={"reason": failed or ""})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\ntranscript: {path}")


asyncio.run(main())



