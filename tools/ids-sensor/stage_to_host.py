"""Stage a large file onto a hypervisor over WinRM as its normal (HyperVAdmin) credential.

HyperVAdmin has no writable share, so SMB is out; this is psfiles' base64-over-PowerShell path,
but with N parallel identity-checked sessions each writing its own byte range (seek, not append),
then the SHA-256 is compared on the host. Audit-logged.

usage: python -I -X utf8 tools/ids-sensor/stage_to_host.py <backend> <host> <local-file> <remote-path> [workers]
"""
import asyncio
import base64
import hashlib
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402
from app.transports.psfiles import ps_literal  # noqa: E402

HOST, LOCAL, REMOTE = sys.argv[2], Path(sys.argv[3]), sys.argv[4]
WORKERS = int(sys.argv[5]) if len(sys.argv) > 5 else 6
CHUNK = 192 * 1024  # keeps each envelope under WinRM's 500 KB default


async def check(tr, cmd: str, what: str) -> str:
    res = await tr.run(cmd, timeout=300)
    if res.exit_code not in (0, None) or res.stderr.strip():
        raise RuntimeError(f"{what}: {res.stderr.strip()[:300]}")
    return res.stdout


async def main() -> None:
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    size = LOCAL.stat().st_size
    p = ps_literal(REMOTE)
    pools = [SessionPool(settings=s, inventory=inv, creds=creds) for _ in range(WORKERS)]
    shells = await asyncio.gather(*(pl.shell(HOST) for pl in pools))

    await check(shells[0],
                f"$p = {p}; $d = Split-Path -Parent $p; "
                "if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }; "
                f"$f = [IO.File]::Open($p, 'Create', 'Write', 'ReadWrite'); try {{ $f.SetLength({size}) }} finally {{ $f.Close() }}",
                "create")

    offsets = list(range(0, size, CHUNK))
    queue: asyncio.Queue[int] = asyncio.Queue()
    for o in offsets:
        queue.put_nowait(o)
    done = 0
    t0 = time.monotonic()

    async def worker(tr) -> None:
        nonlocal done
        with LOCAL.open("rb") as f:
            while not queue.empty():
                off = queue.get_nowait()
                f.seek(off)
                b64 = base64.b64encode(f.read(CHUNK)).decode("ascii")
                await check(tr,
                            f"$b = [Convert]::FromBase64String('{b64}'); "
                            f"$f = [IO.File]::Open({p}, 'Open', 'Write', 'ReadWrite'); "
                            f"try {{ $null = $f.Seek({off}, 'Begin'); $f.Write($b, 0, $b.Length) }} finally {{ $f.Close() }}",
                            f"write@{off}")
                done += 1
                if done % 500 == 0:
                    mb = done * CHUNK / 1e6
                    print(f"  {mb:,.0f} / {size / 1e6:,.0f} MB  {mb / (time.monotonic() - t0):.1f} MB/s", flush=True)

    await asyncio.gather(*(worker(tr) for tr in shells))
    secs = time.monotonic() - t0

    h = hashlib.sha256()
    with LOCAL.open("rb") as f:
        for blk in iter(lambda: f.read(8 << 20), b""):
            h.update(blk)
    remote_hash = (await check(shells[0], f"(Get-FileHash -LiteralPath {p} -Algorithm SHA256).Hash", "hash")).strip()
    ok = remote_hash.lower() == h.hexdigest()
    print(f"{size / 1e6:,.1f} MB in {secs:.0f}s ({size / 1e6 / max(secs, 1):.1f} MB/s); sha256 {'MATCH' if ok else 'MISMATCH'} {remote_hash}")
    AuditLog(s.audit_abs).record(action="ids.stage-file", target=HOST, transport="winrm", result="ok" if ok else "error",
                                 detail={"file": LOCAL.name, "remote": REMOTE, "bytes": size, "sha256": h.hexdigest()})
    for pl in pools:
        await pl.close_all()
    if not ok:
        sys.exit(1)


asyncio.run(main())
