"""SSH / SFTP transport for Linux guests (SINEC INS, Kali).

One persistent asyncssh connection per target; commands and SFTP both multiplex over it, so
a terminal, a fan-out command, and a file copy to the same host share one TCP session.

Auth prefers a private key (from the credentials file) and falls back to a password.
"""

from __future__ import annotations

import time
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
class SSHTransport(Transport):
    port: int = 22
    # "SHA256:..." pin. Checked against the server's key BEFORE authenticating, so a password
    # or key is never offered to an impostor (or to the wrong device after an IP change).
    expected_fingerprint: str | None = None
    _conn: object | None = field(default=None, init=False)

    @property
    def name(self) -> TransportName:
        return TransportName.SSH

    async def connect(self) -> None:
        if self._connected:
            return
        import asyncio

        import asyncssh

        if self.expected_fingerprint:
            try:
                key = await asyncio.wait_for(
                    asyncssh.get_server_host_key(self.address, self.port), timeout=self.connect_timeout)
            except (OSError, asyncio.TimeoutError, asyncssh.Error) as exc:
                raise Unreachable(f"SSH not reachable on {self.address}:{self.port}") from exc
            seen = key.get_fingerprint() if key else "no key"
            if seen != self.expected_fingerprint:
                raise TransportError(
                    f"SSH host key mismatch at {self.address}: got {seen}, inventory pins "
                    f"{self.expected_fingerprint}. No credentials were sent.")

        kwargs: dict = {
            "host": self.address,
            "port": self.port,
            "username": self.credential.username,
            "known_hosts": None,  # TODO(mc01): pin host keys once first-seen on the real lab
        }
        if self.credential.ssh_private_key:
            kwargs["client_keys"] = [asyncssh.import_private_key(self.credential.ssh_private_key)]
        elif self.credential.password:
            kwargs["password"] = self.credential.password

        try:
            self._conn = await asyncio.wait_for(
                asyncssh.connect(**kwargs), timeout=self.connect_timeout
            )
        except asyncssh.PermissionDenied as exc:
            raise AuthError("SSH authentication rejected") from exc
        except (OSError, asyncio.TimeoutError, asyncssh.Error) as exc:
            raise Unreachable(f"SSH not reachable on {self.address}:{self.port}") from exc
        self._connected = True

    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        if not self._connected:
            await self.connect()
        assert self._conn is not None
        start = time.monotonic()
        try:
            result = await self._conn.run(command, timeout=timeout, check=False)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"SSH command failed: {type(exc).__name__}") from exc
        dur = int((time.monotonic() - start) * 1000)
        return CommandResult(
            exit_code=result.exit_status,
            stdout=result.stdout if isinstance(result.stdout, str) else result.stdout.decode(),
            stderr=result.stderr if isinstance(result.stderr, str) else result.stderr.decode(),
            duration_ms=dur,
            transport=self.name,
        )

    async def put_file(self, local_path: str, remote_path: str) -> int:
        await self._ensure()
        async with self._conn.start_sftp_client() as sftp:  # type: ignore[union-attr]
            await sftp.put(local_path, remote_path)
            attrs = await sftp.stat(remote_path)
            return int(attrs.size or 0)

    async def get_file(self, remote_path: str, local_path: str) -> int:
        await self._ensure()
        async with self._conn.start_sftp_client() as sftp:  # type: ignore[union-attr]
            await sftp.get(remote_path, local_path)
            import os

            return os.path.getsize(local_path)

    async def read_bytes(self, remote_path: str) -> bytes:
        await self._ensure()
        remote_path = await self._expand_home(remote_path)
        async with self._conn.start_sftp_client() as sftp:  # type: ignore[union-attr]
            async with sftp.open(remote_path, "rb") as f:
                return await f.read()

    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        await self._ensure()
        import posixpath
        import shlex

        remote_path = await self._expand_home(remote_path)
        parent = posixpath.dirname(remote_path)
        if parent:
            await self._conn.run(f"mkdir -p {shlex.quote(parent)}", check=False)  # type: ignore[union-attr]
        async with self._conn.start_sftp_client() as sftp:  # type: ignore[union-attr]
            async with sftp.open(remote_path, "wb") as f:
                await f.write(data)

    async def _expand_home(self, path: str) -> str:
        """SFTP doesn't expand `~`; its paths are relative to the login dir, so strip `~/`."""
        if path == "~":
            return "."
        if path.startswith("~/"):
            return path[2:]
        return path

    async def _ensure(self) -> None:
        if not self._connected:
            await self.connect()

    async def close(self) -> None:
        if self._conn is not None:
            self._conn.close()  # type: ignore[union-attr]
            await self._conn.wait_closed()  # type: ignore[union-attr]
            self._conn = None
        self._connected = False
