"""SMB transport for bulk file transfer to Windows targets.

Not a shell — this exists so large files go over SMB (fast) instead of being chunked through
WinRM (slow). The session pool pairs it with a WinRM transport for the same target: WinRM for
commands, SMB for files.

TODO(mc01): for hosts with the built-in Administrator disabled, the admin-share connection
must use the host's designated admin account; keep the registered session alive for the whole
transfer (smbprotocol ties opens to the registered session).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from app.models.api import TransportName
from app.transports.base import (
    AuthError,
    CommandResult,
    Transport,
    TransportError,
    Unreachable,
)


@dataclass
class SMBTransport(Transport):
    port: int = 445
    _registered: bool = field(default=False, init=False)

    @property
    def name(self) -> TransportName:
        return TransportName.SMB

    async def connect(self) -> None:
        if self._connected:
            return
        await asyncio.to_thread(self._register_blocking)
        self._connected = True

    def _register_blocking(self) -> None:
        import smbclient
        from smbprotocol.exceptions import SMBAuthenticationError

        try:
            smbclient.register_session(
                self.address,
                username=self.credential.username,
                password=self.credential.password,
                connection_timeout=self.connect_timeout,
            )
        except SMBAuthenticationError as exc:
            raise AuthError("SMB authentication rejected") from exc
        except (OSError, ConnectionError, TimeoutError, ValueError) as exc:
            raise Unreachable(f"SMB not reachable on {self.address}:{self.port}") from exc
        self._registered = True

    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        raise TransportError("SMB transport does not run commands; use WinRM")

    def _unc(self, remote_path: str) -> str:
        r"""Map a local-style path (C:\LabDrop\x) to a UNC admin-share path."""
        drive, rest = os.path.splitdrive(remote_path)
        share = f"{drive[0].lower()}$"  # C: -> c$
        rest = rest.replace("/", "\\").lstrip("\\")
        return rf"\\{self.address}\{share}\{rest}"

    async def put_file(self, local_path: str, remote_path: str) -> int:
        await self._ensure()
        return await asyncio.to_thread(self._put_blocking, local_path, remote_path)

    def _put_blocking(self, local_path: str, remote_path: str) -> int:
        import smbclient

        unc = self._unc(remote_path)
        try:
            smbclient.makedirs(unc.rsplit("\\", 1)[0], exist_ok=True)
        except Exception:  # noqa: BLE001 - dir may already exist
            pass
        written = 0
        with open(local_path, "rb") as src, smbclient.open_file(unc, mode="wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
                written += len(chunk)
        return written

    async def get_file(self, remote_path: str, local_path: str) -> int:
        await self._ensure()
        return await asyncio.to_thread(self._get_blocking, remote_path, local_path)

    def _get_blocking(self, remote_path: str, local_path: str) -> int:
        import smbclient

        unc = self._unc(remote_path)
        read = 0
        with smbclient.open_file(unc, mode="rb") as src, open(local_path, "wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
                read += len(chunk)
        return read

    # Binary modes only: text mode would translate "\n" to os.linesep and corrupt LF content.
    async def read_bytes(self, remote_path: str) -> bytes:
        await self._ensure()
        return await asyncio.to_thread(self._read_bytes_blocking, remote_path)

    def _read_bytes_blocking(self, remote_path: str) -> bytes:
        import smbclient

        with smbclient.open_file(self._unc(remote_path), mode="rb") as f:
            return f.read()

    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        await self._ensure()
        await asyncio.to_thread(self._write_bytes_blocking, remote_path, data)

    def _write_bytes_blocking(self, remote_path: str, data: bytes) -> None:
        import smbclient

        unc = self._unc(remote_path)
        parent = unc.rsplit("\\", 1)[0]
        try:
            smbclient.makedirs(parent, exist_ok=True)
        except Exception:  # noqa: BLE001 - dir may already exist
            pass
        with smbclient.open_file(unc, mode="wb") as f:
            f.write(data)

    async def _ensure(self) -> None:
        if not self._connected:
            await self.connect()

    async def close(self) -> None:
        if self._registered:
            await asyncio.to_thread(self._close_blocking)
        self._connected = False

    def _close_blocking(self) -> None:
        import smbclient

        try:
            smbclient.delete_session(self.address)
        except Exception:  # noqa: BLE001 - best-effort
            pass
        self._registered = False
