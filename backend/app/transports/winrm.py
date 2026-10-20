"""WinRM / PSRP transport for Windows hosts and guests.

Uses pypsrp with NTLM (the only option in this workgroup lab — no Kerberos). A persistent
RunspacePool is opened once in `connect()` and reused for every `run()`, so we never pay
cold-start on each command. pypsrp is synchronous, so calls are pushed to a thread.

TODO(mc01): message encryption is on by default over NTLM; verify against the real hosts that
the negotiated cipher is acceptable and that 5985 (not 5986) is the intended listener.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.models.api import TransportName
from app.transports import psfiles
from app.transports.base import (
    AuthError,
    CommandResult,
    Transport,
    TransportError,
    Unreachable,
)


@dataclass
class WinRMTransport(Transport):
    port: int = 5985
    _pool: object | None = field(default=None, init=False)

    @property
    def name(self) -> TransportName:
        return TransportName.WINRM

    async def connect(self) -> None:
        if self._connected:
            return
        await asyncio.to_thread(self._connect_blocking)
        self._connected = True

    def _connect_blocking(self) -> None:
        from pypsrp.exceptions import AuthenticationError, WinRMTransportError
        from pypsrp.powershell import RunspacePool
        from pypsrp.wsman import WSMan

        try:
            wsman = WSMan(
                self.address,
                port=self.port,
                username=self.credential.username,
                password=self.credential.password,
                auth="ntlm",
                encryption="auto",
                ssl=False,
                connection_timeout=self.connect_timeout,
            )
            pool = RunspacePool(wsman)
            pool.open()
        except AuthenticationError as exc:
            raise AuthError("NTLM authentication rejected") from exc
        except (WinRMTransportError, ConnectionError, OSError, TimeoutError) as exc:
            raise Unreachable(f"WinRM not reachable on {self.address}:{self.port}") from exc
        self._pool = pool

    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        if not self._connected:
            await self.connect()
        return await asyncio.to_thread(self._run_blocking, command, timeout)

    def _run_blocking(self, command: str, timeout: int) -> CommandResult:
        from pypsrp.powershell import PowerShell

        assert self._pool is not None
        start = time.monotonic()
        ps = PowerShell(self._pool)  # type: ignore[arg-type]
        ps.add_script(_formatted(command))
        try:
            output = ps.invoke()
        except Exception as exc:  # noqa: BLE001 - normalise to our error type
            raise TransportError(f"command invocation failed: {type(exc).__name__}") from exc
        dur = int((time.monotonic() - start) * 1000)
        stdout = "\n".join(str(o) for o in output)
        stderr = "\n".join(str(e) for e in ps.streams.error)
        exit_code = 1 if ps.had_errors else 0
        return CommandResult(exit_code, stdout, stderr, dur, self.name)

    # Slow-path file I/O through the command channel (SMB is preferred by the pool).
    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        await psfiles.write_bytes(self.run, remote_path, data)

    async def read_bytes(self, remote_path: str) -> bytes:
        return await psfiles.read_bytes(self.run, remote_path)

    async def put_file(self, local_path: str, remote_path: str) -> int:
        return await psfiles.put_file(self.run, local_path, remote_path)

    async def get_file(self, remote_path: str, local_path: str) -> int:
        return await psfiles.get_file(self.run, remote_path, local_path)

    async def close(self) -> None:
        if self._pool is not None:
            await asyncio.to_thread(self._close_blocking)
        self._connected = False

    def _close_blocking(self) -> None:
        try:
            self._pool.close()  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 - closing is best-effort
            pass
        self._pool = None


def _formatted(script: str) -> str:
    """Make PSRP output read like a console.

    PSRP returns objects, and str() of a deserialised object is just its type name. If the
    script emits only strings/primitives they pass through untouched (base64 file chunks and
    ConvertTo-Json output must stay exact); otherwise the whole output goes through
    Out-String so tables/lists render as PowerShell would print them. Dot-sourcing keeps
    variables alive in the runspace between terminal commands.
    """
    # `.PSObject.BaseObject` matters for PowerShell Direct: strings coming back from
    # Invoke-Command carry PSComputerName/RunspaceId note properties, and pypsrp decodes such a
    # decorated string as a complex object whose str() is 'None'. The base object is plain.
    return (
        "$__lc = @(. {\n" + script + "\n}); "
        "if (@($__lc | Where-Object { $_ -isnot [string] -and $_ -isnot [ValueType] }).Count) "
        "{ $__lc | Out-String -Width 250 } else { $__lc | ForEach-Object { $_.PSObject.BaseObject } }"
    )
