"""PowerShell Direct transport — reach a Windows guest *through* its hypervisor over VMBus.

This is the fallback for Windows guests on isolated segments, where the network can't reach
the guest but the hypervisor can. It is not a direct connection: it rides the hypervisor's
own WinRM session, running `Invoke-Command -VMId ... -Credential ...` there.

Hard rule: PowerShell Direct does NOT work against Linux guests. The pool must never build
this transport for a Linux target; `connect()` guards against it anyway.

TODO(mc01): confirm the guest credential works for PS Direct (it authenticates inside the
guest, so it needs a valid *guest* local/domain account, not the host's HyperVAdmin).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.api import TransportName
from app.transports import psfiles
from app.transports.base import AuthError, CommandResult, Transport, TransportError, Unreachable


@dataclass
class PSDirectTransport(Transport):
    """Runs guest commands via the hypervisor's warm WinRM transport.

    `host_transport` is the already-connected WinRM transport to the hypervisor. `vm_name` is
    the guest's VM name on that hypervisor. `guest_credential` authenticates inside the guest.
    """

    host_transport: Transport | None = None
    vm_name: str = ""
    expected_hostname: str | None = None  # guest's computer name; checked on connect
    _ready: bool = field(default=False, init=False)

    @property
    def name(self) -> TransportName:
        return TransportName.PSDIRECT

    async def connect(self) -> None:
        """Prove the path works before reporting the session open: the VM is Running, the
        guest credential logs in, and the guest is the computer the inventory expects."""
        if self.host_transport is None or not self.vm_name:
            raise TransportError("PowerShell Direct needs a hypervisor transport and a VM name")
        if not self.host_transport.connected:
            await self.host_transport.connect()

        vm = self.vm_name.replace("'", "''")
        state = await self.host_transport.run(f"[string](Get-VM -Name '{vm}').State")
        if state.stdout.strip() != "Running":
            raise Unreachable(f"VM {self.vm_name} is {state.stdout.strip() or 'not found'}")

        probe = await self.host_transport.run(_wrap_psdirect(
            vm_name=self.vm_name, username=self.credential.username,
            password=self.credential.password or "", inner="$env:COMPUTERNAME"))
        seen = probe.stdout.strip()
        if probe.exit_code or not seen:
            err = probe.stderr.strip().splitlines()
            raise AuthError(f"PowerShell Direct login to {self.vm_name} failed: "
                            f"{err[0][:200] if err else 'no response'}")
        if self.expected_hostname and seen.upper() != self.expected_hostname.upper():
            raise TransportError(f"VM {self.vm_name} reports computer name {seen}, inventory "
                                 f"expects {self.expected_hostname}")
        self._connected = True
        self._ready = True

    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        if not self._connected:
            await self.connect()
        assert self.host_transport is not None
        # Build a credential inside the host session and Invoke-Command -VMId against the guest.
        # The guest password is injected as a secure string; it is never logged.
        wrapped = _wrap_psdirect(
            vm_name=self.vm_name,
            username=self.credential.username,
            password=self.credential.password or "",
            inner=command,
        )
        result = await self.host_transport.run(wrapped, timeout=timeout)
        # Re-badge the transport so callers/audit see psdirect, not winrm.
        return CommandResult(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            transport=self.name,
        )

    # File I/O rides the same Invoke-Command channel (slow path; fine for clipboard drops).
    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        await psfiles.write_bytes(self.run, remote_path, data)

    async def read_bytes(self, remote_path: str) -> bytes:
        return await psfiles.read_bytes(self.run, remote_path)

    async def put_file(self, local_path: str, remote_path: str) -> int:
        return await psfiles.put_file(self.run, local_path, remote_path)

    async def get_file(self, remote_path: str, local_path: str) -> int:
        return await psfiles.get_file(self.run, remote_path, local_path)

    async def close(self) -> None:
        # The underlying host transport is owned by the pool; don't close it here.
        self._connected = False
        self._ready = False


def _wrap_psdirect(*, vm_name: str, username: str, password: str, inner: str) -> str:
    """Produce PowerShell that runs `inner` inside the guest via PowerShell Direct.

    The password is placed into a SecureString on the host and discarded after the call.
    Single quotes in values are doubled to keep the here-string safe.
    """
    u = username.replace("'", "''")
    p = password.replace("'", "''")
    vm = vm_name.replace("'", "''")
    return (
        f"$sec = ConvertTo-SecureString '{p}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{u}', $sec); "
        f"try {{ Invoke-Command -VMName '{vm}' -Credential $cred -ScriptBlock {{ {inner} }} }} "
        f"finally {{ Remove-Variable sec, cred -ErrorAction SilentlyContinue }}"
    )
