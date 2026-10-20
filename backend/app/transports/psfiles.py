"""Byte-exact file I/O over a PowerShell command channel (WinRM, PowerShell Direct).

This is the SLOW path — base64 chunks inside PowerShell commands — used for small files
(clipboard drops) and as the last-resort fallback when SMB isn't reachable. Bulk copies go
over SMB/SFTP (REQUIREMENTS §3). Bytes are never re-encoded, so line endings and encodings
survive exactly.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Awaitable, Callable, Iterable

from app.transports.base import CommandResult, TransportError

RunFn = Callable[[str], Awaitable[CommandResult]]

# Raw bytes per command. Base64 inflates by 4/3; this keeps each envelope well under
# WinRM's default 500 KB MaxEnvelopeSizekb.
CHUNK = 192 * 1024


def ps_literal(value: str) -> str:
    """A single-quoted PowerShell string literal."""
    return "'" + value.replace("'", "''") + "'"


async def _check(run: RunFn, command: str, what: str) -> CommandResult:
    res = await run(command)
    if res.exit_code not in (0, None):
        raise TransportError(f"{what} failed: {res.stderr.strip()[:300]}")
    return res


async def _write_chunks(run: RunFn, remote_path: str, chunks: Iterable[bytes]) -> int:
    p = ps_literal(remote_path)
    create = (
        f"$p = {p}; $d = Split-Path -Parent $p; "
        "if ($d -and -not (Test-Path -LiteralPath $d)) "
        "{ New-Item -ItemType Directory -Force -Path $d | Out-Null }; "
    )
    # Always create/truncate first, so an empty source still yields an empty file.
    await _check(run, create + "[IO.File]::WriteAllBytes($p, [byte[]]@())", "write")
    written = 0
    for chunk in chunks:
        if not chunk:
            continue
        b64 = base64.b64encode(chunk).decode("ascii")
        cmd = (
            f"$p = {p}; $b = [Convert]::FromBase64String('{b64}'); "
            "$f = [IO.File]::Open($p, 'Append'); try { $f.Write($b, 0, $b.Length) } "
            "finally { $f.Close() }"
        )
        await _check(run, cmd, "write")
        written += len(chunk)
    return written


async def write_bytes(run: RunFn, remote_path: str, data: bytes) -> None:
    await _write_chunks(run, remote_path, (data[i : i + CHUNK] for i in range(0, len(data), CHUNK)))


async def read_bytes(run: RunFn, remote_path: str) -> bytes:
    p = ps_literal(remote_path)
    out = bytearray()
    while True:
        cmd = (
            f"$f = [IO.File]::OpenRead({p}); try {{ $null = $f.Seek({len(out)}, 'Begin'); "
            f"$buf = New-Object byte[] {CHUNK}; $n = $f.Read($buf, 0, {CHUNK}); "
            "[Convert]::ToBase64String($buf, 0, $n) } finally { $f.Close() }"
        )
        res = await _check(run, cmd, "read")
        chunk = base64.b64decode(res.stdout.strip() or "")
        out += chunk
        if len(chunk) < CHUNK:
            return bytes(out)


async def put_file(run: RunFn, local_path: str, remote_path: str) -> int:
    with open(local_path, "rb") as f:
        return await _write_chunks(run, remote_path, iter(lambda: f.read(CHUNK), b""))


async def get_file(run: RunFn, remote_path: str, local_path: str) -> int:
    data = await read_bytes(run, remote_path)
    with open(local_path, "wb") as f:
        f.write(data)
    return os.path.getsize(local_path)
