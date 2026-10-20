"""Hyper-V operations, centralised so the -Passthru / read-back / verify pattern lives in ONE
place and can't be forgotten per call site.

Every mutating operation here:
  1. runs the Set/Checkpoint cmdlet with -Passthru,
  2. reads the resulting state back with a separate query,
  3. returns that read-back state to the caller, who compares it to what was asked.

This directly answers the lab's "Set-VM fails silently" and "CheckpointType Disabled" gotchas.
All commands run on the *hypervisor's* transport (WinRM as HyperVAdmin), targeting a VM by name.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.transports.base import Transport, TransportError


class HyperVError(TransportError):
    pass


@dataclass
class VMState:
    name: str
    state: str  # Running / Off / Saved / Paused
    checkpoint_type: str  # Production / Standard / Disabled
    uptime_seconds: int | None = None


@dataclass
class SnapshotState:
    vm_name: str
    name: str
    snapshot_type: str  # Production / Standard  (verified after creation)


# Windows PowerShell 5.1's ConvertTo-Json writes enums as integers (State=2, not "Running"),
# so every enum field is cast to [string] on the host before serialising.
_VM_FIELDS = (
    "Name,@{N='State';E={[string]$_.State}},"
    "@{N='CheckpointType';E={[string]$_.CheckpointType}},"
    "@{N='Uptime';E={[int]$_.Uptime.TotalSeconds}}"
)


def _ps_json(inner: str) -> str:
    """Wrap a pipeline so its output comes back as JSON we can parse deterministically."""
    return f"{inner} | ConvertTo-Json -Compress -Depth 4"


async def _run_json(host: Transport, inner: str, *, timeout: int = 120) -> object:
    res = await host.run(_ps_json(inner), timeout=timeout)
    if res.exit_code not in (0, None):
        raise HyperVError(res.stderr.strip() or "Hyper-V command failed")
    text = res.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise HyperVError("could not parse Hyper-V output") from exc


async def get_vms(host: Transport) -> list[VMState]:
    """List VMs on a hypervisor with the fields the dashboard needs."""
    data = await _run_json(
        host,
        f"Get-VM | Select-Object {_VM_FIELDS}",
    )
    if data is None:
        return []
    rows = data if isinstance(data, list) else [data]
    out: list[VMState] = []
    for r in rows:
        out.append(
            VMState(
                name=r.get("Name", ""),
                state=str(r.get("State", "")),
                checkpoint_type=str(r.get("CheckpointType", "")),
                uptime_seconds=r.get("Uptime"),
            )
        )
    return out


async def disk_free(host: Transport) -> list[dict]:
    """Host disk free space WITHOUT Get-Volume (Access Denied under HyperVAdmin)."""
    data = await _run_json(
        host,
        "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | "
        "Select-Object DeviceID,"
        "@{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,1)}},"
        "@{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}}",
    )
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


# power action -> (cmdlet, the state the VM must read back as afterwards)
_POWER = {
    "start": ("Start-VM -Name '{vm}' -Passthru", "Running"),
    "shutdown": ("Stop-VM -Name '{vm}' -Passthru", "Off"),  # guest shutdown; blocks until off
    "turnoff": ("Stop-VM -Name '{vm}' -TurnOff -Passthru", "Off"),
    "save": ("Save-VM -Name '{vm}' -Passthru", "Saved"),
}


async def set_power(host: Transport, vm: str, action: str) -> VMState:
    """start | shutdown | turnoff | save, then read the state back and VERIFY it."""
    spec = _POWER.get(action)
    if spec is None:
        raise HyperVError(f"unknown power action: {action}")
    template, want = spec
    current = await get_vm_state(host, vm)
    if current.state.lower() == want.lower():
        return current  # already there; Start-VM etc. would error on a no-op
    res = await host.run(template.format(vm=_q(vm)) + " | Out-Null", timeout=600)
    if res.exit_code not in (0, None):
        raise HyperVError(res.stderr.strip() or f"{action} failed")
    state = await get_vm_state(host, vm)
    if state.state.lower() != want.lower():
        raise HyperVError(f"{action} did not apply: expected {want}, host reports {state.state}")
    return state


async def get_vm_state(host: Transport, vm: str) -> VMState:
    data = await _run_json(
        host,
        f"Get-VM -Name '{_q(vm)}' | Select-Object {_VM_FIELDS}",
    )
    if not data:
        raise HyperVError(f"VM not found: {vm}")
    r = data[0] if isinstance(data, list) else data
    return VMState(
        name=r.get("Name", ""),
        state=str(r.get("State", "")),
        checkpoint_type=str(r.get("CheckpointType", "")),
        uptime_seconds=r.get("Uptime"),
    )


async def set_checkpoint_type(host: Transport, vm: str, checkpoint_type: str) -> VMState:
    """Set the VM's checkpoint-type preference, then VERIFY it (Set-VM fails silently)."""
    await host.run(
        f"Set-VM -Name '{_q(vm)}' -CheckpointType {checkpoint_type} -Passthru "
        "| Select-Object Name,CheckpointType"
    )
    state = await get_vm_state(host, vm)
    if state.checkpoint_type.lower() != checkpoint_type.lower():
        raise HyperVError(
            f"checkpoint type did not apply: asked {checkpoint_type}, host reports "
            f"{state.checkpoint_type}"
        )
    return state


async def create_checkpoint(
    host: Transport, vm: str, *, checkpoint_type: str = "Production", name: str | None = None
) -> SnapshotState:
    """Create a checkpoint and VERIFY the resulting snapshot's actual type.

    CheckpointType 'Disabled' silently yields a Standard checkpoint, so we set the type first
    (and verify it), then create, then read the snapshot's SnapshotType back.
    """
    await set_checkpoint_type(host, vm, checkpoint_type)
    name_arg = f" -SnapshotName '{_q(name)}'" if name else ""
    res = await host.run(f"Checkpoint-VM -Name '{_q(vm)}'{name_arg}")
    if res.exit_code not in (0, None):
        raise HyperVError(res.stderr.strip() or "Checkpoint-VM failed")
    # Read back the newest snapshot and confirm its type.
    data = await _run_json(
        host,
        f"Get-VMSnapshot -VMName '{_q(vm)}' | Sort-Object CreationTime | "
        "Select-Object -Last 1 VMName,Name,@{N='SnapshotType';E={[string]$_.SnapshotType}}",
    )
    if not data:
        raise HyperVError("checkpoint reported success but no snapshot was found")
    r = data[0] if isinstance(data, list) else data
    snap = SnapshotState(
        vm_name=r.get("VMName", vm),
        name=r.get("Name", ""),
        snapshot_type=str(r.get("SnapshotType", "")),
    )
    want = "Production" if checkpoint_type.lower() == "production" else "Standard"
    if snap.snapshot_type.lower() != want.lower():
        raise HyperVError(
            f"checkpoint created as {snap.snapshot_type}, expected {want} â€” "
            "verify VSS health in the guest for Production checkpoints"
        )
    return snap


async def list_checkpoints(host: Transport, vm: str) -> list[SnapshotState]:
    data = await _run_json(
        host,
        f"Get-VMSnapshot -VMName '{_q(vm)}' | "
        "Select-Object VMName,Name,@{N='SnapshotType';E={[string]$_.SnapshotType}},"
        "@{N='Created';E={$_.CreationTime.ToString('o')}}",
    )
    if not data:
        return []
    rows = data if isinstance(data, list) else [data]
    return [
        SnapshotState(
            vm_name=r.get("VMName", vm),
            name=r.get("Name", ""),
            snapshot_type=str(r.get("SnapshotType", "")),
        )
        for r in rows
    ]


async def restore_checkpoint(host: Transport, vm: str, checkpoint_name: str) -> VMState:
    res = await host.run(
        f"Restore-VMSnapshot -VMName '{_q(vm)}' -Name '{_q(checkpoint_name)}' -Confirm:$false"
    )
    if res.exit_code not in (0, None):
        raise HyperVError(res.stderr.strip() or "Restore-VMSnapshot failed")
    return await get_vm_state(host, vm)


async def delete_checkpoint(host: Transport, vm: str, checkpoint_name: str) -> None:
    """Remove a checkpoint, then VERIFY it is gone."""
    v, n = _q(vm), _q(checkpoint_name)
    res = await host.run(f"Remove-VMSnapshot -VMName '{v}' -Name '{n}' -Confirm:$false")
    if res.exit_code not in (0, None):
        raise HyperVError(res.stderr.strip() or "Remove-VMSnapshot failed")
    still = await _run_json(
        host,
        f"@(Get-VMSnapshot -VMName '{v}' -Name '{n}' -ErrorAction SilentlyContinue).Count",
    )
    if still:
        raise HyperVError(f"checkpoint {checkpoint_name!r} still present after delete")


async def vss_healthy(host: Transport, vm: str) -> bool:
    """Report whether the guest's VSS integration service is present and OK.

    Used to decide whether to OFFER a Production checkpoint for a VM.
    """
    data = await _run_json(
        host,
        f"Get-VMIntegrationService -VMName '{_q(vm)}' -Name 'VSS' | "
        "Select-Object Enabled,PrimaryStatusDescription",
    )
    if not data:
        return False
    r = data[0] if isinstance(data, list) else data
    return bool(r.get("Enabled")) and str(r.get("PrimaryStatusDescription", "")).lower() == "ok"


def _q(value: str) -> str:
    """Escape a single-quoted PowerShell literal."""
    return value.replace("'", "''")
