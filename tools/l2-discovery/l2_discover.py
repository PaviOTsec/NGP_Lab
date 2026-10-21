"""Read-only L2 discovery (rule 13 "handle with care", rule 14 observe-only).

  1. L2-HOST-1: NTLM identity check (no credentials) -> WinRM login as HyperVAdmin ->
     Get-VM + Get-VMNetworkAdapter (names, state, MACs, IPs, switch). Nothing is changed.
  2. Each L2 guest address from the inventory (+ the unidentified .20.13/.14 and L2BM_BR):
     credential-free NTLM NEGOTIATE to WinRM 5985 -> NetBIOS / DNS name. No login.

One device at a time; every step goes to the audit log. Output JSON goes to
%LOCALAPPDATA%\\LabConsole\\l2-discovery\\<stamp>.json.

usage: python -I -X utf8 tools/l2-discovery/l2_discover.py <backend>
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core import identity  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory, TargetKind  # noqa: E402

HOST = "L2-HOST-1"
EXTRA = ["192.168.20.13", "192.168.20.14"]  # unidentified Hyper-V VMs on the System network

VM_PS = (
    "Get-VM | ForEach-Object { $vm = $_; [pscustomobject]@{"
    " Name = $vm.Name; State = [string]$vm.State; Uptime = [int]$vm.Uptime.TotalSeconds;"
    " Generation = $vm.Generation; CheckpointType = [string]$vm.CheckpointType;"
    " Adapters = @(Get-VMNetworkAdapter -VM $vm | ForEach-Object { [pscustomobject]@{"
    "  Mac = $_.MacAddress; Switch = $_.SwitchName; IPs = @($_.IPAddresses) } }) } }"
    " | ConvertTo-Json -Compress -Depth 5"
)


async def main() -> None:
    s = Settings.load()
    audit = AuditLog(s.audit_abs)
    inv = Inventory.load(s.inventory_path)
    pool = SessionPool(settings=s, inventory=inv,
                       creds=CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml"))
    out: dict = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "host": HOST, "vms": None, "identities": {}}

    # 1. the hypervisor (pool checks the NTLM identity before the login)
    try:
        host = await pool.hypervisor_shell(HOST)
        res = await host.run(VM_PS, timeout=120)
        if res.exit_code not in (0, None):
            raise RuntimeError(res.stderr.strip()[:300])
        data = json.loads(res.stdout.strip() or "[]")
        out["vms"] = data if isinstance(data, list) else [data]
        audit.record(action="l2-discovery.get-vm", target=HOST, transport=str(host.name), result="ok",
                     detail={"vms": len(out["vms"])})
    except Exception as exc:  # noqa: BLE001
        out["vms_error"] = f"{type(exc).__name__}: {exc}"
        audit.record(action="l2-discovery.get-vm", target=HOST, transport="winrm", result="failed",
                     detail={"error": out["vms_error"][:200]})
    finally:
        await pool.close_all()

    # 2. credential-free identity of each L2 Windows address, one at a time
    addrs = [(t.name, t.address) for t in inv.all()
             if t.ot and t.os.value == "windows" and t.kind != TargetKind.HYPERVISOR and t.address]
    addrs += [(f"unlisted@{a}", a) for a in EXTRA]
    for name, addr in addrs:
        try:
            ident = await identity.probe_identity(addr, timeout=5.0)
            out["identities"][name] = {"address": addr, "computer": ident.computer, "domain": ident.domain,
                                       "dns_computer": ident.dns_computer, "dns_domain": ident.dns_domain}
            result = "ok"
        except Exception as exc:  # noqa: BLE001
            out["identities"][name] = {"address": addr, "error": str(exc)[:200]}
            result = "failed"
        audit.record(action="l2-discovery.identity-probe", target=name, transport="ntlm-negotiate",
                     result=result, detail={"address": addr})

    d = Path(os.environ["LOCALAPPDATA"]) / "LabConsole" / "l2-discovery"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"saved {f}")


asyncio.run(main())
