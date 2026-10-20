"""Text-into-VM helpers that ride the lab sessions (REQUIREMENTS §4a).

  * type_into_vm  — types text into a VM's virtual keyboard via Msvm_Keyboard.TypeText on the
                    hypervisor. Works at logon screens, on Linux consoles, on appliances, on
                    isolated guests, any OS/state. ASCII + US-layout only; length-capped.
  * type_credential_into_vm — same, with a password taken from the loaded credentials file.
  * push_to_vm    — write bytes (a clipboard item, converted for the target OS) to a file on
                    the target over the fastest file transport, byte-exact.
  * pull_from_vm  — read a file back from the target.

The shared clipboard board itself (browser page for the VMs) lives in app.core.clipstore.
A direct Set-Clipboard-over-WinRM push is intentionally NOT provided: it fills session 0's
clipboard (invisible to the interactive user) and Linux servers have no GUI clipboard.
"""

from __future__ import annotations

import posixpath

from app.core.hyperv import _q
from app.core.pool import SessionPool
from app.models.inventory import OS, Target
from app.transports.base import TransportError


class VMTextError(TransportError):
    pass


async def type_into_vm(pool: SessionPool, target: Target, *, text: str, max_chars: int) -> None:
    """Type `text` into the VM via its hypervisor's Msvm_Keyboard. Caller enforces focus."""
    if not text:
        return
    if len(text) > max_chars:
        raise VMTextError(f"text exceeds the {max_chars}-char type limit; push it as a file instead")
    if not _is_ascii(text):
        raise VMTextError("Type into VM is ASCII-only (US layout); push it as a file instead")

    host_transport = await pool.hypervisor_shell(target.name)
    script = _type_text_script(vm_name=target.vm_name or target.name, text=text)
    res = await host_transport.run(script)
    if res.exit_code not in (0, None):
        raise VMTextError(res.stderr.strip() or "TypeText failed")


async def type_credential_into_vm(
    pool: SessionPool, target: Target, *, entry: str, which: str = "password", max_chars: int = 512
) -> None:
    """Type a password (or username) from the credentials file into the VM."""
    cred = pool.creds.credential(entry)
    value = cred.password if which == "password" else cred.username
    if not value:
        raise VMTextError(f"credential {entry!r} has no {which}")
    await type_into_vm(pool, target, text=value, max_chars=max_chars)


def default_drop_path(target: Target, filename: str, windows_dir: str, linux_dir: str) -> str:
    if target.os == OS.LINUX:
        return posixpath.join(linux_dir.rstrip("/"), filename)
    return windows_dir.rstrip("\\") + "\\" + filename


async def push_to_vm(pool: SessionPool, target: Target, *, data: bytes, remote_path: str) -> str:
    transport = await pool.file_transport(target.name)
    await transport.write_bytes(remote_path, data)
    return transport.name


async def pull_from_vm(pool: SessionPool, target: Target, *, remote_path: str) -> bytes:
    transport = await pool.file_transport(target.name)
    return await transport.read_bytes(remote_path)


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _type_text_script(*, vm_name: str, text: str) -> str:
    """PowerShell that sends `text` to the VM's synthetic keyboard via WMI.

    Msvm_Keyboard.TypeText takes the whole string at once. We locate the keyboard through the
    VM's Msvm_ComputerSystem so we never type into the wrong VM.
    """
    safe = text.replace("'", "''")
    vm = _q(vm_name)
    return (
        f"$vm = Get-CimInstance -Namespace root\\virtualization\\v2 -ClassName Msvm_ComputerSystem "
        f"-Filter \"ElementName='{vm}'\"; "
        "if (-not $vm) { throw 'VM not found' }; "
        "$kb = Get-CimAssociatedInstance -InputObject $vm -ResultClassName Msvm_Keyboard; "
        f"Invoke-CimMethod -InputObject $kb -MethodName TypeText -Arguments @{{ asciiText = '{safe}' }} "
        "| Out-Null"
    )
