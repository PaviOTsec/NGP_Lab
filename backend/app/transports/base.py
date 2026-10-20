"""The Transport interface.

Every way of reaching a target — WinRM, SSH, SMB, PowerShell Direct — implements this. Routes
and the action engine never touch an implementation directly; they ask the session pool for a
connected Transport and use this surface. That keeps transport choice and the warm-session
logic in one place and makes the whole layer unit-testable with mocks.

Design notes:
- A Transport instance is bound to one target and one credential. It is created disconnected;
  `connect()` establishes the warm session and is idempotent.
- Implementations are async. Blocking client libraries (pypsrp, smbprotocol) are run in a
  thread via `asyncio.to_thread` inside the implementation, so callers always await.
- Credentials come from the loaded credentials file (app.core.credentials) via the pool.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from app.models.api import TransportName


@dataclass
class Credential:
    """A login for one target, from the credentials file. Held in backend memory while loaded."""

    username: str
    password: str | None = None
    ssh_private_key: str | None = None  # PEM/OpenSSH text from the credentials file
    # The credentials entry name this came from, for the audit log (never the password).
    source_entry: str = ""

    def redacted(self) -> str:
        return f"<cred {self.username!r} from {self.source_entry!r}>"


@dataclass
class CommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    transport: TransportName


class TransportError(Exception):
    """Base for all transport failures. Messages must be secret-free."""


class AuthError(TransportError):
    """Authentication was rejected (e.g. NTLM failure, bad SSH key)."""


class Unreachable(TransportError):
    """The target could not be reached within the connect timeout."""


@dataclass
class Transport(abc.ABC):
    """Abstract connection to one target."""

    target_name: str
    address: str
    credential: Credential
    connect_timeout: int = 5
    _connected: bool = field(default=False, init=False)

    @property
    @abc.abstractmethod
    def name(self) -> TransportName: ...

    @property
    def connected(self) -> bool:
        return self._connected

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish the warm session. Idempotent; raises AuthError / Unreachable on failure."""

    @abc.abstractmethod
    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        """Run a command on the target over the warm session and return its result."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down the session. Safe to call more than once."""

    # --- optional capabilities; default to "not supported" ---

    async def put_file(self, local_path: str, remote_path: str) -> int:
        """Upload a file, returning bytes written. Override where the transport supports it."""
        raise TransportError(f"{self.name} does not support file upload")

    async def get_file(self, remote_path: str, local_path: str) -> int:
        """Download a file, returning bytes read. Override where the transport supports it."""
        raise TransportError(f"{self.name} does not support file download")

    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        """Write bytes to a remote file exactly as given (no newline/encoding translation)."""
        raise TransportError(f"{self.name} does not support writing files")

    async def read_bytes(self, remote_path: str) -> bytes:
        """Read a remote file's bytes exactly."""
        raise TransportError(f"{self.name} does not support reading files")

    async def read_text_file(self, remote_path: str) -> str:
        """Read a small UTF-8 text file. Line endings are returned untouched."""
        data = await self.read_bytes(remote_path)
        return data.decode("utf-8-sig", errors="replace")

    async def write_text_file(self, remote_path: str, text: str) -> None:
        """Write a small UTF-8 text file. Line endings are written untouched."""
        await self.write_bytes(remote_path, text.encode("utf-8"))
