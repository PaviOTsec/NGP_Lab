"""Trainee Wi-Fi: read-only capture of the SCALANCE WAM763-1 AP (rule-13 exception, 2026-10-13).

Only `show ...` commands are ever sent (anything else is refused before connecting). Host key
pinned on the authenticating connection; one login attempt; passwords never printed.
Writes raw + cleaned text per command, a SHA-256 manifest, and an audit record.

usage: python -I -X utf8 ap_readonly.py <backend_dir> <out_dir> [show-command ...]
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(BACKEND))

import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402

NAME, IP = "WAP", "192.168.20.30"
FP = "SHA256:jR+A8QW1WF3uTHH4V/d8hDOhJc3yuPCfXraztLwo+ZE"  # ecdsa-sha2-nistp521, first seen 2026-10-13;
# identity cross-checked via WBM TLS cert: ScalanceW700 SN(VPU3627519) MAC(74FC45B5A0B0)
CREDENTIAL = "network/admin"

DEFAULT = [
    "show versions",
    "show running-config all",
    "show running-config",
    "show wlan overview",
    "show wlan device",
    "show wlan basic",
    "show wlan advanced",
    "show wlan ap",
    "show wlan vap",
    "show wlan security",
    "show wlan client-list",
    "show wlan client-list-vap",
    "show vlan",
    "show vlan port config",
    "show vlan device info",
    "show mac-address-table",
    "show ip route",
    "show ip arp",
    "show ip dhcp-server pools",
    "show access-lists",
    "show interface access lists",
]
CMDS = sys.argv[3:] or DEFAULT

PROMPT = re.compile(r"(?i)cli(\([\w-]+\))?[#>]\s*$")
MORE = re.compile(r"--\s*More\s*--")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


async def run_cmd(proc, cmd: str, maxwait: float = 300.0) -> str:
    proc.stdin.write(cmd + "\n")
    buf, loop = "", asyncio.get_running_loop()
    end = loop.time() + maxwait
    while loop.time() < end:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(65536), timeout=4.0)
        except asyncio.TimeoutError:
            if PROMPT.search(ANSI.sub("", buf).rstrip()):
                return buf
            continue
        if not chunk:
            break
        buf += chunk
        if MORE.search(ANSI.sub("", buf[-200:])):
            proc.stdin.write(" ")
    return buf + "\n[TIMEOUT]"


def clean(raw: str, cmd: str) -> str:
    t = ANSI.sub("", raw)
    t = re.sub(r"--\s*More\s*--[ \r\x08]*", "", t)
    t = t.replace("\r\n", "\n").replace("\r", "")
    t = t.split("\n", 1)[1] if t.lstrip().startswith(cmd) else t
    lines = t.rstrip().split("\n")
    if lines and PROMPT.search(lines[-1]):
        lines = lines[:-1]
    return "\n".join(lines).strip("\n") + "\n"


async def main() -> None:
    bad = [c for c in CMDS if not c.startswith("show ")]
    if bad:
        sys.exit(f"refusing non-show commands: {bad}")
    OUT.mkdir(parents=True, exist_ok=True)
    cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential(CREDENTIAL)
    audit = AuditLog(Settings.load().audit_abs)
    key = await asyncio.wait_for(asyncssh.get_server_host_key(IP, 22), 15)
    if key is None or key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncio.wait_for(asyncssh.connect(
        IP, username=cred.username, password=cred.password, known_hosts=([key], [], []),
        client_keys=None, agent_path=None), 30)
    files = []
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(400, 60))
        banner = await run_cmd(proc, "", maxwait=25)
        print("first prompt:", ANSI.sub("", banner).strip().splitlines()[-1:] or "?")
        for cmd in CMDS:
            raw = await run_cmd(proc, cmd)
            text = clean(raw, cmd)
            stem = f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_{re.sub(r'[^a-z0-9]+', '-', cmd.lower()).strip('-')}.txt"
            (OUT / (stem + ".raw")).write_text(raw, encoding="utf-8", newline="")
            (OUT / stem).write_text(text, encoding="utf-8", newline="\n")
            err = bool(re.search(r"(?i)invalid|unknown command|incomplete|not available", text[:400]))
            files.append({"cmd": cmd, "file": stem, "lines": text.count("\n"), "timeout": "[TIMEOUT]" in raw,
                          "cli_error": err, "sha256": hashlib.sha256(text.encode()).hexdigest()})
            print(f"{cmd:32} {text.count(chr(10)):5}l{' TIMEOUT' if '[TIMEOUT]' in raw else ''}{' CLI-ERROR' if err else ''}")
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    (OUT / f"{NAME}_{IP}_{time.strftime('%Y%m%d-%H%M%S')}_manifest.json").write_text(
        json.dumps({"device": NAME, "address": IP, "fp": FP, "files": files}, indent=1), encoding="utf-8")
    audit.record(action="trainee-wifi.ap-readonly", target=NAME, transport="ssh", result="ok",
                 detail={"commands": CMDS})


asyncio.run(main())
