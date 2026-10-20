"""FW-South (PAN-OS 11.1): enable LLDP on ethernet1/3 (-> SW-Ops) and ethernet1/4 (-> SW-DMZ) so the
SCALANCE neighbours (and SINEC NMS through them) see the firewall. Approved by the operator 2026-10-12.
Same gates as nms_apply_panos.py: no pending changes before -> set -> diff gate (only LLDP keys,
no removals) -> commit; `revert config` on any error/unexpected diff. ethernet1/5 (FortiGate) and
ethernet1/6 (L2 side) are deliberately left without LLDP.
usage: python -I nms_apply_panos_lldp.py <backend_dir> <out_dir> [--dry-run]"""
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
P = "set network profiles lldp-profile NMS-LLDP"
COMMANDS = [
    "set network lldp enable yes",
    f"{P} mode transmit-receive",
    f"{P} option-tlvs system-name yes",
    f"{P} option-tlvs system-description yes",
    f"{P} option-tlvs port-description yes",
    f"{P} option-tlvs system-capabilities yes",
    f"{P} option-tlvs management-address enabled yes",
    f"{P} option-tlvs management-address iplist nms-mgmt interface ethernet1/4 ipv4 10.1.20.254/24",
    "set network interface ethernet ethernet1/3 layer3 lldp enable yes profile NMS-LLDP",
    "set network interface ethernet ethernet1/4 layer3 lldp enable yes profile NMS-LLDP",
]
KEYS = {"network", "lldp", "enable", "profiles", "lldp-profile", "NMS-LLDP", "mode", "option-tlvs", "system-name",
        "system-description", "port-description", "system-capabilities", "management-address", "enabled", "iplist",
        "nms-mgmt", "interface", "ipv4", "10.1.20.254/24", "profile", "ethernet", "ethernet1/3", "ethernet1/4",
        "layer3", "}"}


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
                failed = cmd; print("!!! error:", out.strip()[:300]); break
        diff = await send(proc, "run show config diff") if not failed else ""
        log.append(">>> run show config diff\n" + diff.strip())
        changed = [ln for ln in diff.splitlines() if re.match(r"^\s*[+-]", ln)]
        # The only removals allowed: the two per-interface flags "lldp { enable no; }" flipping to yes.
        flips = [ln for ln in changed if re.fullmatch(r"-\s*enable no;", ln.strip())]
        bad = [ln for ln in changed if ln not in flips and (ln.lstrip().startswith("-")
               or re.split(r"[\s;{]+", ln.lstrip("+ ").strip())[0] not in KEYS)]
        if len(flips) > 2:
            bad += flips
        print("diff changed lines:", len(changed), "| unexpected:", bad[:5])
        if failed or not changed or bad or DRY:
            reason = failed or ("dry-run" if DRY else "unexpected/empty diff")
            print("REVERT:", reason)
            log.append(">>> revert config\n" + (await send(proc, "revert config")).strip())
            failed = failed or reason
        else:
            res = await send(proc, 'commit description "SINEC NMS topology: LLDP on eth1/3 + eth1/4"', maxwait=600)
            log.append(">>> commit\n" + res.strip())
            print("commit:", " ".join(res.split())[:300])
            committed = bool(re.search(r"(?i)committed successfully|commit job .* (complete|succeeded)", res))
            if not committed:
                failed = "commit did not report success"
                log.append(">>> revert config (after failed commit)\n" + (await send(proc, "revert config")).strip())
                print("commit failed -> candidate reverted")
        await send(proc, "exit")
        if committed:
            await asyncio.sleep(45)  # let one LLDP transmit interval pass before reading neighbours
        log.append("\n===== VERIFY =====")
        for v in ("show config diff", "show lldp config all", "show lldp neighbors all", "show interface all"):
            out = await send(proc, v)
            log.append(f">>> {v}\n{out.strip()}")
            if v != "show interface all":
                print(f">>> {v}\n{out.strip()[:2500]}")
        proc.stdin.write("exit\n"); await asyncio.sleep(0.5)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_lldp-apply-transcript.txt"
    path.write_text("\n".join(log) + "\n", encoding="utf-8")
    AuditLog(Settings.load().audit_abs).record(action="nms-topology.apply-panos-lldp", target=NAME, transport="ssh",
                                               result="committed" if committed else "reverted", detail={"reason": failed or ""})
    print(f"\nRESULT: {'COMMITTED' if committed else 'NOT committed (' + str(failed) + ')'}\ntranscript: {path}")


asyncio.run(main())
