"""Look at / type into a VM's console through its hypervisor (Hyper-V WMI, as HyperVAdmin).

  screen <target> <out.png>     Msvm_VirtualSystemManagementService.GetVirtualSystemThumbnailImage
  type   <target> <text>        vmtext.type_into_vm (Msvm_Keyboard.TypeText)
  enter  <target>               Msvm_Keyboard.TypeKey(VK_RETURN)

usage: python -I -X utf8 tools/ids-sensor/vm_console.py <backend> <action> <target> [arg]
"""
import asyncio
import base64
import struct
import sys
import zlib
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.core.vmtext import type_into_vm  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

ACTION, TARGET = sys.argv[2], sys.argv[3]
W, H = 1024, 768


def _vm_cim(vm: str) -> str:
    v = vm.replace("'", "''")
    return (f"$vm = Get-CimInstance -Namespace root\\virtualization\\v2 -ClassName Msvm_ComputerSystem "
            f"-Filter \"ElementName='{v}'\"; if (-not $vm) {{ throw 'VM not found' }}; ")


def _png(rgb565: bytes, w: int, h: int) -> bytes:
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            (p,) = struct.unpack_from("<H", rgb565, (y * w + x) * 2)
            rows += bytes((((p >> 11) & 31) * 255 // 31, ((p >> 5) & 63) * 255 // 63, (p & 31) * 255 // 31))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))


async def main() -> None:
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    pool = SessionPool(settings=s, inventory=inv, creds=CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml"))
    target = next(t for t in inv.all() if t.name == TARGET)
    vm = target.vm_name or target.name
    if ACTION == "screen":
        host = await pool.hypervisor_shell(target.name)
        res = await host.run(
            _vm_cim(vm)
            + "$sd = Get-CimAssociatedInstance -InputObject $vm -ResultClassName Msvm_VirtualSystemSettingData | "
              "Where-Object VirtualSystemType -eq 'Microsoft:Hyper-V:System:Realized'; "
              "$svc = Get-CimInstance -Namespace root\\virtualization\\v2 -ClassName Msvm_VirtualSystemManagementService; "
              f"$r = Invoke-CimMethod -InputObject $svc -MethodName GetVirtualSystemThumbnailImage -Arguments @{{ TargetSystem = $sd; WidthPixels = [uint16]{W}; HeightPixels = [uint16]{H} }}; "
              "[Convert]::ToBase64String([byte[]]$r.ImageData)", timeout=120)
        raw = base64.b64decode(res.stdout.strip() or "")
        if len(raw) < W * H * 2:
            raise SystemExit(f"thumbnail failed ({len(raw)} bytes): {res.stderr.strip()[:300]}")
        Path(sys.argv[4]).write_bytes(_png(raw[: W * H * 2], W, H))  # Hyper-V appends a few trailer bytes
        print(f"saved {sys.argv[4]}")
        return
    if ACTION == "type":
        await type_into_vm(pool, target, text=sys.argv[4], max_chars=512)
    elif ACTION in ("enter", "keys"):
        # keys: letters/digits as virtual-key presses (VK code = uppercase ASCII), then Enter
        codes = [ord(c) for c in sys.argv[4].upper()] if ACTION == "keys" else []
        codes.append(13)
        host = await pool.hypervisor_shell(target.name)
        res = await host.run(_vm_cim(vm) + "$kb = Get-CimAssociatedInstance -InputObject $vm -ResultClassName Msvm_Keyboard; "
                             + "".join(f"Invoke-CimMethod -InputObject $kb -MethodName TypeKey -Arguments @{{ keyCode = [uint32]{c} }} | Out-Null; Start-Sleep -Milliseconds 150; "
                                       for c in codes))
        if res.exit_code not in (0, None) or res.stderr.strip():
            raise SystemExit(res.stderr.strip()[:300])
    else:
        raise SystemExit(f"unknown action {ACTION}")
    AuditLog(s.audit_abs).record(action=f"vm.console-{ACTION}", target=target.name, transport="hyperv-wmi", result="ok",
                                 detail={"chars": len(sys.argv[4]) if ACTION == "type" else 1})
    print("ok")


asyncio.run(main())
