"""SINEC NMS onboarding, phase 3: CLI configuration backups.

Per device, over SSH (host key pinned on the authenticating connection):
  SCALANCE : show versions, show running-config all, show running-config
  FortiGate: get system status, show (non-default config), show full-configuration
  PAN-OS   : show system info, running config as XML (session output format only),
             `show config diff` in configure mode (must be empty: no pending candidate
             changes), and `save config to <name>` = a named snapshot ON the firewall
             (writes a file; does not change running or candidate config).
Writes raw + cleaned text, SHA-256 manifest, and a completeness check per file.
No VM checkpoints, ever.

usage: python -I nms_backup.py <backend_dir> <out_dir> [device | name=ip=ssh_fp ...]
  name=ip=ssh_fp = a SCALANCE outside the inventory (rule-13 exceptions), pinned by host key.
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
OFF_INV = [a.split("=", 2) for a in sys.argv[3:] if "=" in a]
ONLY = {a for a in sys.argv[3:] if "=" not in a} | {n for n, _, _ in OFF_INV}
sys.path.insert(0, str(BACKEND))

import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

STAMP = time.strftime("%Y%m%d")
PAN_SNAPSHOT = __import__("os").environ.get("PAN_SNAPSHOT_NAME") or f"nms-pre-onboarding-{STAMP}.xml"

# (command, artifact-name or None, completeness regex for the cleaned output)
PLAN: dict[str, list[tuple[str, str | None, str | None]]] = {
    "scalance": [
        ("show versions", "versions.txt", r"Firmware_Running"),
        ("show running-config all", "running-config-all.txt", r"(?m)^end\s*$"),
        ("show running-config", "running-config.txt", r"(?m)^end\s*$"),
    ],
    "fortigate": [
        ("get system status", "system-status.txt", r"Version: FortiGate"),
        ("show", "config.txt", r"(?s)config system global.*\nend\s*$"),
        ("show full-configuration", "full-configuration.txt", r"(?s)config system global.*\nend\s*$"),
    ],
    "paloalto": [
        ("set cli pager off", None, None),
        ("show system info", "system-info.txt", r"sw-version"),
        # byte-exact XML + pending-changes check come from pan_export.py (XML API)
        ("show config running", "running-config-cli-text.txt", r"(?s)^config \{.*\}\s*$"),
        ("configure", None, None),
        (f"save config to {PAN_SNAPSHOT}", "snapshot-save.txt", r"(?i)saved|success"),
        ("exit", None, None),
    ],
}
EXTRA = [{"name": "OT-FW", "address": "192.168.20.254", "vendor": "scalance",
          "fp": "SHA256:2McI2gqY7nMsRn0UFk4UboOwsSh4Pjf6bF0xmWxnzgY", "credential": "network/admin"}] + [
    {"name": n, "address": ip, "vendor": "scalance", "fp": fp, "credential": "network/admin"} for n, ip, fp in OFF_INV]

PROMPT = re.compile(r"(CLI(\([\w-]+\))?#|FortiGate[\w-]* [#$]|@PA-[\w-]+[>#])\s*$")
MORE = re.compile(r"--\s*More\s*--")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


async def run_cmd(proc, cmd: str, maxwait: float = 600.0) -> str:
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


def clean(raw: str, cmd: str, vendor: str) -> str:
    t = ANSI.sub("", raw)
    t = re.sub(r"--\s*More\s*--[ \r\x08]*", "", t)
    t = t.replace("\r\n", "\n").replace("\r", "")
    if vendor == "paloalto":  # PAN redraws the line while typing; drop echo up to the command
        t = re.sub(r"(?s)^.*?" + re.escape(cmd) + r"\n", "", t, count=1)
    else:
        t = t.split("\n", 1)[1] if t.startswith(cmd) or t.lstrip().startswith(cmd) else t
    lines = t.rstrip().split("\n")
    if lines and PROMPT.search(lines[-1]):  # drop trailing prompt
        lines = lines[:-1]
    return "\n".join(lines).strip("\n") + "\n"


async def backup(dev: dict, cred, audit: AuditLog) -> dict:
    name, addr, fp, vendor = dev["name"], dev["address"], dev["fp"], dev["vendor"]
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    key = await asyncio.wait_for(asyncssh.get_server_host_key(addr, 22), 10)
    if key.get_fingerprint() != fp:
        return {"device": name, "ok": False, "error": "host key mismatch; no credentials sent"}
    conn = await asyncio.wait_for(asyncssh.connect(
        addr, username=cred.username, password=cred.password, known_hosts=([key], [], []),
        client_keys=None, agent_path=None), 20)
    files, ok = [], True
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(400, 60))
        await run_cmd(proc, "", maxwait=25)  # banner + first prompt
        for cmd, art, check in PLAN[vendor]:
            raw = await run_cmd(proc, cmd)
            if not art:
                continue
            text = clean(raw, cmd, vendor)
            art = f"{name}_{addr}_{time.strftime('%Y%m%d-%H%M%S')}_{art}"  # device_ip_time_content
            (d / (art + ".raw")).write_text(raw, encoding="utf-8", newline="")
            (d / art).write_text(text, encoding="utf-8", newline="\n")
            good = bool(text.strip()) and "[TIMEOUT]" not in raw and (not check or re.search(check, text) is not None)
            ok &= good
            files.append({"file": art, "bytes": len(text.encode()), "lines": text.count("\n"),
                          "sha256": hashlib.sha256(text.encode()).hexdigest(), "complete": good})
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
    finally:
        conn.close()
    res = {"device": name, "address": addr, "vendor": vendor, "ok": ok, "files": files}
    (d / f"{name}_{addr}_{time.strftime('%Y%m%d-%H%M%S')}_manifest.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    audit.record(action="nms-phase3.backup", target=name, transport="ssh", result="ok" if ok else "incomplete",
                 detail={"files": [f["file"] for f in files]})
    return res


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    audit = AuditLog(settings.audit_abs)
    # default: the NMS set; devices named on the command line may be any network device (e.g. SW-Mgmt)
    devs = [{"name": t.name, "address": t.address, "vendor": t.vendor, "fp": t.ssh_fingerprint,
             "credential": t.credential} for t in inv.all()
            if t.kind == "network" and (t.name in ONLY if ONLY else "nms" in t.tags)] + EXTRA
    if ONLY:
        devs = [d for d in devs if d["name"] in ONLY]
    results = await asyncio.gather(*(backup(d, creds.credential(d["credential"]), audit) for d in devs),
                                   return_exceptions=True)
    for d, r in zip(devs, results):
        if isinstance(r, BaseException):
            print(f"{d['name']:9} FAILED {type(r).__name__}")
            continue
        print(f"{r['device']:9} {'OK ' if r['ok'] else 'BAD'} " + "  ".join(
            f"{f['file']}={f['lines']}l{'' if f['complete'] else '(!)'}" for f in r.get("files", [])) + (f" {r.get('error','')}"))


asyncio.run(main())
