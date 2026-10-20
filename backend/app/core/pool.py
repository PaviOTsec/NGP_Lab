"""The session pool — the heart of the console's speed.

Responsibilities:
  * Build the right Transport for each target+operation from the inventory, route, and the
    fallback order in REQUIREMENTS §3: the DIRECT link first whenever the target has an
    address, the Hyper-V link (PowerShell Direct via its hypervisor) only after that.
  * Open connections in parallel at load and keep them WARM for reuse.
  * Hand out a connected transport for "shell", "file", or "hyperv" work without the caller
    knowing which protocol won.
  * Keep host-admin sessions separate from the HyperVAdmin ones, so a declared host-level
    action never silently runs as (or widens) HyperVAdmin.
  * Drop everything on unload.

The pool owns transports; callers borrow them and must not close them.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.config import Settings
from app.core import identity
from app.core.credentials import CredentialStore
from app.models.api import ConnState, SessionStatus, TransportName
from app.models.inventory import OS, Access, Inventory, Route, Target, TargetKind
from app.transports.base import AuthError, Credential, Transport, TransportError, Unreachable
from app.transports.psdirect import PSDirectTransport
from app.transports.smb import SMBTransport
from app.transports.ssh import SSHTransport
from app.transports.winrm import WinRMTransport


class CredClass:
    """Which credential an operation runs under. Actions/playbook steps declare this."""

    DEFAULT = "default"  # the target's own credential (HyperVAdmin on hypervisors)
    HOST_ADMIN = "host-admin"  # the hypervisor's separate local Administrator entry


@dataclass
class TargetConns:
    """The live transports held for one target."""

    shell: Transport | None = None
    admin_shell: Transport | None = None
    file: Transport | None = None
    status: SessionStatus | None = None


@dataclass
class SessionPool:
    settings: Settings
    inventory: Inventory
    creds: CredentialStore
    _conns: dict[str, TargetConns] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _credential(self, entry: str) -> Credential:
        return self.creds.credential(entry)

    def _conns_for(self, target: Target) -> TargetConns:
        return self._conns.setdefault(target.name, TargetConns())

    # --- warm-up ---

    async def warm_all(self) -> list[SessionStatus]:
        """Open shell transports to every configured, reachable target in parallel."""
        # Network devices connect on demand (playbooks): switches have few vty lines, and a
        # warm session per device would hold one for the whole shift.
        targets = [
            t for t in self.inventory.all()
            if t.configured and t.access != Access.POWER_ONLY and t.os != OS.APPLIANCE
            and t.kind != TargetKind.NETWORK
        ]
        results = await asyncio.gather(*(self._warm_one(t) for t in targets), return_exceptions=True)
        statuses: list[SessionStatus] = []
        for t, res in zip(targets, results):
            if isinstance(res, SessionStatus):
                statuses.append(res)
            else:
                statuses.append(
                    SessionStatus(
                        target=t.name,
                        transport=TransportName.NONE,
                        state=ConnState.FAILED,
                        detail=_safe_detail(res),
                    )
                )
        return statuses

    async def _warm_one(self, target: Target) -> SessionStatus:
        conns = self._conns_for(target)
        try:
            transport = await self._open_shell(target)
            status = SessionStatus(target=target.name, transport=transport.name, state=ConnState.OPEN)
        except TransportError as exc:
            status = SessionStatus(
                target=target.name,
                transport=TransportName.NONE,
                state=ConnState.FAILED,
                detail=_safe_detail(exc),
            )
        conns.status = status
        return status

    # --- transport construction (selection + fallback) ---

    async def _open_shell(self, target: Target) -> Transport:
        """Return a connected shell transport, trying the fallback order for the target."""
        conns = self._conns_for(target)
        if conns.shell and conns.shell.connected:
            return conns.shell

        reasons: list[str] = []
        for builder in self._shell_plan(target):
            try:
                transport = await builder()
                await transport.connect()
                conns.shell = transport
                conns.status = SessionStatus(
                    target=target.name, transport=transport.name, state=ConnState.OPEN
                )
                return transport
            except TransportError as exc:
                reasons.append(_safe_detail(exc))
                continue
        detail = "; ".join(reasons) if reasons else "no transport applies to this target"
        raise Unreachable(f"no shell transport reached {target.name} ({detail})")

    def _direct_ok(self, target: Target) -> bool:
        """The direct link is tried whenever there's an address and the route doesn't forbid it."""
        return bool(target.address) and target.route != Route.VIA_HOST

    def _shell_plan(self, target: Target):
        """Ordered list of zero-arg async builders to try for a shell, per REQUIREMENTS §3."""
        plans = []

        if target.os in (OS.LINUX, OS.NETWORK):
            if self._direct_ok(target):
                plans.append(lambda: self._build_ssh(target))
            # PowerShell Direct never applies to Linux / network devices (hard rule 9).
            return plans

        if target.os == OS.WINDOWS:
            if self._direct_ok(target):
                plans.append(lambda: self._build_winrm(target, target.credential))
            # Hyper-V link: PowerShell Direct via the guest's hypervisor.
            if target.kind == TargetKind.GUEST and target.host:
                plans.append(lambda: self._build_psdirect(target))
            return plans

        # appliances have no shell (hard rule 5)
        return plans

    async def _build_winrm(self, target: Target, entry: str) -> Transport:
        # Ask the host who it is before any credential leaves MC01 (drawing IPs have drifted:
        # "DMZ-HOST-2"'s address was really L2-HOST-1). A failed probe counts as "direct link
        # unavailable", so the plan falls through to the Hyper-V link.
        ident = await identity.probe_identity(
            target.address, timeout=self.settings.sessions.connect_timeout_seconds)
        identity.check(target.expected_hostname, ident, target.address)
        return WinRMTransport(
            target_name=target.name,
            address=target.address,
            credential=self._credential(entry),
            connect_timeout=self.settings.sessions.connect_timeout_seconds,
        )

    async def _build_ssh(self, target: Target) -> Transport:
        cred = self._credential(target.credential)
        if target.user and not cred.username:
            cred = Credential(
                username=target.user,
                password=cred.password,
                ssh_private_key=cred.ssh_private_key,
                source_entry=cred.source_entry,
            )
        return SSHTransport(
            target_name=target.name,
            address=target.address,
            credential=cred,
            connect_timeout=self.settings.sessions.connect_timeout_seconds,
            expected_fingerprint=target.ssh_fingerprint,
        )

    async def _build_psdirect(self, target: Target) -> Transport:
        host = self.inventory.hypervisor_for(target)
        if host is None:
            raise TransportError(f"no hypervisor known for {target.name}")
        host_transport = await self._open_shell(host)  # reuse the warm host session
        return PSDirectTransport(
            target_name=target.name,
            address=target.address or target.name,
            credential=self._credential(target.credential),
            host_transport=host_transport,
            vm_name=target.vm_name or target.name,
            expected_hostname=target.hostname,
        )

    async def _open_admin_shell(self, target: Target) -> Transport:
        """A WinRM session to a hypervisor under its separate host-admin credential."""
        if not target.is_hypervisor:
            raise TransportError(f"host-admin credential applies to hypervisors only, not {target.name}")
        if not target.admin_credential:
            raise TransportError(f"{target.name} has no admin_credential in the inventory")
        conns = self._conns_for(target)
        if conns.admin_shell and conns.admin_shell.connected:
            return conns.admin_shell
        transport = await self._build_winrm(target, target.admin_credential)
        await transport.connect()
        conns.admin_shell = transport
        return transport

    # --- public borrow API ---

    async def shell(self, target_name: str, cred_class: str = CredClass.DEFAULT) -> Transport:
        target = self._require(target_name)
        if target.access == Access.POWER_ONLY or target.os == OS.APPLIANCE:
            raise TransportError(f"{target.name} is power-only; no shell is offered")
        if cred_class == CredClass.HOST_ADMIN:
            return await self._open_admin_shell(target)
        if cred_class != CredClass.DEFAULT:
            raise TransportError(f"unknown credential class: {cred_class}")
        return await self._open_shell(target)

    async def file_transport(self, target_name: str) -> Transport:
        """A transport for bulk file transfer: SMB (Windows) or SFTP (Linux) first, direct only.

        Falls back to the shell transport, whose PowerShell-based copy is chunked and slower.
        TODO(mc01): Copy-VMFile via the hypervisor for isolated guests (stage to host first).
        """
        target = self._require(target_name)
        conns = self._conns_for(target)
        if conns.file and conns.file.connected:
            return conns.file

        if target.os == OS.WINDOWS and self._direct_ok(target):
            smb = SMBTransport(
                target_name=target.name,
                address=target.address,
                credential=self._credential(target.credential),
                connect_timeout=self.settings.sessions.connect_timeout_seconds,
            )
            try:
                # Same identity gate as WinRM before SMB sends the credential.
                identity.check(target.expected_hostname, await identity.probe_identity(
                    target.address, timeout=self.settings.sessions.connect_timeout_seconds),
                    target.address)
                await smb.connect()
                conns.file = smb
                return smb
            except TransportError:
                pass  # fall through to the shell transport's copy path

        # Linux → the SSH transport already does SFTP; Windows fallback → whatever shell we have.
        transport = await self.shell(target_name)
        conns.file = transport
        return transport

    async def hypervisor_shell(self, target_name: str) -> Transport:
        """The transport for Hyper-V actions: always the hypervisor that runs the target."""
        target = self._require(target_name)
        host = self.inventory.hypervisor_for(target)
        if host is None:
            raise TransportError(f"no hypervisor known for {target_name}")
        return await self._open_shell(host)

    # --- status + teardown ---

    def statuses(self) -> list[SessionStatus]:
        return [c.status for c in self._conns.values() if c.status is not None]

    def status_for(self, target_name: str) -> SessionStatus | None:
        conns = self._conns.get(target_name)
        return conns.status if conns else None

    async def close_all(self) -> None:
        """Close every transport."""
        async with self._lock:
            transports: list[Transport] = []
            for conns in self._conns.values():
                for t in (conns.shell, conns.admin_shell, conns.file):
                    if t is not None and t not in transports:
                        transports.append(t)
            await asyncio.gather(*(t.close() for t in transports), return_exceptions=True)
            self._conns.clear()

    def _require(self, target_name: str) -> Target:
        target = self.inventory.by_name(target_name)
        if target is None:
            raise TransportError(f"unknown target: {target_name}")
        return target


def _safe_detail(exc: object) -> str:
    """A short reason string for the UI."""
    if isinstance(exc, AuthError):
        return "authentication rejected"
    if isinstance(exc, TransportError):
        return str(exc)[:300]
    return f"error: {type(exc).__name__}"
