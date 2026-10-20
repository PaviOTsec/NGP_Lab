"""Tests for the Hyper-V verification logic — the core defence against 'Set-VM fails silently'."""

from __future__ import annotations

import pytest

from app.core import hyperv
from app.core.hyperv import HyperVError
from tests.mocks import make, result, vm_json


async def test_create_checkpoint_verifies_production_type():
    """A Production checkpoint that comes back Production succeeds."""
    host = make(
        responses=[
            ("Get-VM -Name", vm_json("Running", "Production")),
            ("Get-VMSnapshot", result('{"VMName":"VM1","Name":"snap1","SnapshotType":"Production"}')),
        ]
    )
    snap = await hyperv.create_checkpoint(host, "VM1", checkpoint_type="Production")
    assert snap.snapshot_type == "Production"


async def test_create_checkpoint_rejects_silent_standard():
    """If the checkpoint silently comes back Standard, we raise rather than report success."""
    host = make(
        responses=[
            ("Get-VM -Name", vm_json("Running", "Production")),
            ("Get-VMSnapshot", result('{"VMName":"VM1","Name":"snap1","SnapshotType":"Standard"}')),
        ]
    )
    with pytest.raises(HyperVError) as exc:
        await hyperv.create_checkpoint(host, "VM1", checkpoint_type="Production")
    assert "expected Production" in str(exc.value)


async def test_set_checkpoint_type_detects_silent_failure():
    """Set-VM returns no error but the readback shows the type didn't change -> raise."""
    host = make(responses=[("Get-VM -Name", vm_json("Off", "Disabled"))])
    with pytest.raises(HyperVError) as exc:
        await hyperv.set_checkpoint_type(host, "VM1", "Production")
    assert "did not apply" in str(exc.value)


async def test_enum_fields_are_stringified_on_the_host():
    """PS 5.1 ConvertTo-Json emits enums as ints; every query must cast them to [string]."""
    host = make(responses=[("Get-VM -Name", vm_json("Running"))])
    await hyperv.get_vm_state(host, "VM1")
    assert "[string]$_.State" in host.calls[0]
    assert "[string]$_.CheckpointType" in host.calls[0]


async def test_power_start_verifies_running():
    host = make(responses=[("Get-VM -Name", [vm_json("Off"), vm_json("Running")])])
    st = await hyperv.set_power(host, "VM1", "start")
    assert st.state == "Running"
    assert any("Start-VM" in c and "-Passthru" in c for c in host.calls)


async def test_power_start_silent_failure_raises():
    """Start-VM reports no error but the VM is still Off -> raise, don't report success."""
    host = make(responses=[("Get-VM -Name", vm_json("Off"))])
    with pytest.raises(HyperVError) as exc:
        await hyperv.set_power(host, "VM1", "start")
    assert "expected Running" in str(exc.value)


async def test_power_already_in_state_is_a_noop():
    host = make(responses=[("Get-VM -Name", vm_json("Running"))])
    await hyperv.set_power(host, "VM1", "start")
    assert not any("Start-VM" in c for c in host.calls)


async def test_power_error_stream_raises():
    host = make(responses=[("Get-VM -Name", vm_json("Off")),
                           ("Start-VM", result(exit_code=1, stderr="not enough memory"))])
    with pytest.raises(HyperVError, match="not enough memory"):
        await hyperv.set_power(host, "VM1", "start")


async def test_disk_free_uses_logicaldisk_not_getvolume():
    host = make(responses=[("Win32_LogicalDisk", result('{"DeviceID":"C:","FreeGB":40.0,"SizeGB":120.0}'))])
    disks = await hyperv.disk_free(host)
    assert disks and disks[0]["DeviceID"] == "C:"
    assert "Get-Volume" not in " ".join(host.calls)
