"""SINEC NMS onboarding, phase 1: READ-ONLY discovery.

- Logs into each NMS-tagged network device (+ the OT firewall exception) over SSH with the
  host key pinned ON THE AUTHENTICATING CONNECTION, runs show/get commands only, saves output.
- From the NMS host (DMZH2_MaintServer, via the console's session pool = identity-checked),
  tests reachability to each device and reads routes / SNMP UDP listeners.
Nothing here changes configuration. Passwords are never printed or written.

usage: python -I nms_phase1.py <backend_dir> <out_dir> [devices|devices2|topo|reach|all]
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
MODE = sys.argv[3] if len(sys.argv) > 3 else "all"
sys.path.insert(0, str(BACKEND))

import asyncssh  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

CREDS_FILE = BACKEND.parent / "config" / "credentials.example.yaml"

# Read-only commands per CLI dialect. Unknown commands just return an error.
COMMANDS: dict[str, list[str]] = {
    "scalance": [
        "show versions", "show ?",
        "show snmp", "show snmp community", "show snmp user", "show snmp group",
        "show snmp viewtree", "show snmp targetaddr", "show snmp targetparam",
        "show lldp", "show running-config",
    ],
    "fortigate": [
        "get system status",
        "show system snmp sysinfo", "show system snmp community", "show system snmp user",
        "show system interface",
    ],
    "paloalto": [
        "set cli pager off",  # session-only CLI setting, not configuration
        "show system info",
        "show config running xpath devices/entry/deviceconfig/system/snmp-setting",
        "show config running xpath devices/entry/deviceconfig/system/service",
        "show config running xpath devices/entry/deviceconfig/system/permitted-ip",
        "show config running xpath devices/entry/network/profiles/interface-management-profile",
        "show lldp config all",
    ],
}
COMMANDS2: dict[str, list[str]] = {
    "scalance": [
        "show running-config snmp all", "show snmp engineID", "show snmp notif",
        "show lldp status", "show events config", "show ip http secure server status",
    ],
    "fortigate": ["get system snmp sysinfo"],
    "paloalto": [
        "set cli pager off",
        "show config running xpath devices/entry/network/interface/ethernet",
        "show interface management",
    ],
}
# Cabling evidence for the NMS topology: who is plugged in where (LLDP + MAC/ARP tables).
COMMANDS_TOPO: dict[str, list[str]] = {
    "scalance": [
        "show lldp neighbors detail", "show mac-address-table", "show interfaces description",
        "show ip interface",
    ],
    "fortigate": [
        "get system interface physical", "diagnose lldprx neighbor summary",
        "show full-configuration system global | grep lldp", "get system arp",
    ],
    "paloalto": [
        "set cli pager off",
        "show lldp config all", "show lldp neighbors all", "show interface all", "show arp all",
    ],
}
if MODE == "devices2":
    COMMANDS = COMMANDS2
elif MODE == "topo":
    COMMANDS = COMMANDS_TOPO
# OT firewall: rule-13 exception, deliberately not in the inventory.
EXTRA = [{"name": "OT-FW", "address": "192.168.20.254", "vendor": "scalance",
          "fp": "SHA256:2McI2gqY7nMsRn0UFk4UboOwsSh4Pjf6bF0xmWxnzgY",
          "credential": "network/admin"}]

PROMPT = re.compile(r"[\w\-\.\(\)@:/ ]{1,80}[>#$]\s*$")
MORE = re.compile(r"(--\s*More\s*--|<--- More --->|\(more\)|Press any key)", re.I)


async def read_quiet(proc, idle: float = 2.0, maxwait: float = 60.0) -> str:
    buf, start = "", time.monotonic()
    while time.monotonic() - start < maxwait:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(65536), timeout=idle)
        except asyncio.TimeoutError:
            last = buf.rstrip("\r\n").rsplit("\n", 1)[-1]
            if PROMPT.search(last) or not buf:
                if buf:
                    return buf
            continue
        if not chunk:
            break
        buf += chunk
        if MORE.search(buf[-120:]):
            proc.stdin.write(" ")
    return buf


async def run_device(dev: dict, cred, audit: AuditLog) -> str:
    name, addr, fp = dev["name"], dev["address"], dev["fp"]
    key = await asyncio.wait_for(asyncssh.get_server_host_key(addr, 22), 10)
    seen = key.get_fingerprint() if key else "no key"
    if seen != fp:
        audit.record(action="nms-phase1.show", target=name, transport="ssh", result="host-key-mismatch")
        return f"{name}: HOST KEY MISMATCH ({seen} != {fp}); no credentials sent"
    # Pin on the authenticating connection: only this exact key is accepted.
    conn = await asyncio.wait_for(asyncssh.connect(
        addr, username=cred.username, password=cred.password,
        known_hosts=([key], [], []), client_keys=None, agent_path=None), 20)
    log = []
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        log.append(await read_quiet(proc, idle=3.0, maxwait=25))
        for cmd in COMMANDS[dev["vendor"]]:
            proc.stdin.write(cmd + "\n")
            log.append(f"\n===== {cmd} =====\n")
            log.append(await read_quiet(proc, idle=2.5, maxwait=90))
        proc.stdin.write("exit\n")
        await asyncio.sleep(0.5)
        proc.close()
    finally:
        conn.close()
    text = "".join(log).replace("\r\n", "\n")
    suffix = {"devices2": "-2", "topo": "-topo"}.get(MODE, "")
    (OUT / f"{name}{suffix}.txt").write_text(text, encoding="utf-8")
    audit.record(action="nms-phase1.show", target=name, transport="ssh", result="ok",
                 detail={"commands": len(COMMANDS[dev["vendor"]]), "bytes": len(text)})
    return f"{name}: ok, {len(text)} bytes -> {name}.txt"


async def devices(inv: Inventory, creds: CredentialStore, audit: AuditLog) -> None:
    devs = [{"name": t.name, "address": t.address, "vendor": t.vendor,
             "fp": t.ssh_fingerprint, "credential": t.credential}
            for t in inv.all() if "nms" in t.tags and t.kind == "network"] + EXTRA
    results = await asyncio.gather(
        *(run_device(d, creds.credential(d["credential"]), audit) for d in devs),
        return_exceptions=True)
    for d, r in zip(devs, results):
        print(r if isinstance(r, str) else f"{d['name']}: FAILED {type(r).__name__}: {r}")


REACH_PS = r"""
$ips = '__IPS__'.Split(',')
'--- IPv4 addresses'; Get-NetIPAddress -AddressFamily IPv4 | ? IPAddress -ne '127.0.0.1' | % { "$($_.InterfaceAlias)  $($_.IPAddress)/$($_.PrefixLength)" }
'--- IPv4 routes'; Get-NetRoute -AddressFamily IPv4 | ? { $_.DestinationPrefix -notmatch '^(224|255|127)' } | % { "$($_.DestinationPrefix) via $($_.NextHop) if=$($_.InterfaceAlias)" }
'--- UDP 161/162 listeners'; Get-NetUDPEndpoint -ErrorAction SilentlyContinue | ? { $_.LocalPort -in 161,162 } | % { "$($_.LocalAddress):$($_.LocalPort) pid=$($_.OwningProcess) $((Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName)" }
'--- reachability (ping / tcp22 / tcp443)'
foreach ($ip in $ips) {
  $p = Test-Connection -ComputerName $ip -Count 2 -Quiet -ErrorAction SilentlyContinue
  $t = foreach ($port in 22,443) { $c = New-Object Net.Sockets.TcpClient; $ok = $c.ConnectAsync($ip,$port).Wait(2000) -and $c.Connected; $c.Close(); "$port=$ok" }
  "$ip ping=$p $($t -join ' ')"
}
"""


async def reach(inv: Inventory, creds: CredentialStore, settings: Settings, audit: AuditLog) -> None:
    from app.core.pool import SessionPool
    ips = [t.address for t in inv.all() if "nms" in t.tags and t.kind == "network"]
    ips += [d["address"] for d in EXTRA]
    nms = next(t for t in inv.all() if t.name == "DMZH2_MaintServer")
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    tr = await pool._open_shell(nms)
    res = await tr.run(REACH_PS.replace("__IPS__", ",".join(ips)), timeout=300)
    text = (res.stdout or "") + ("\n[stderr]\n" + res.stderr if res.stderr else "")
    (OUT / "reachability_from_nms.txt").write_text(text, encoding="utf-8")
    audit.record(action="nms-phase1.reachability", target=nms.name, transport=str(tr.name), result="ok")
    print(text)
    try:
        await tr.close()
    except Exception:  # noqa: BLE001
        pass


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(CREDS_FILE)
    audit = AuditLog(settings.audit_abs)
    if MODE in ("devices", "devices2", "topo", "all"):
        await devices(inv, creds, audit)
    if MODE in ("reach", "all"):
        await reach(inv, creds, settings, audit)


asyncio.run(main())
