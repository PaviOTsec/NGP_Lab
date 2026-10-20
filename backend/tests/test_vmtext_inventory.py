"""VM text helpers (type-into-VM guards, push/pull) and inventory parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import vmtext
from app.core.vmtext import VMTextError, _type_text_script
from app.models.inventory import Inventory
from tests.mocks import make

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "inventory.example.yaml"


class _StubPool:
    def __init__(self):
        self.host = make("DMZ-HOST-1")
        self.files = make("guest")

    async def hypervisor_shell(self, name):  # noqa: ARG002
        return self.host

    async def file_transport(self, name):  # noqa: ARG002
        return self.files


async def test_type_into_vm_rejects_non_ascii():
    t = Inventory.load(EXAMPLE).by_name("DMZH2_DC")
    with pytest.raises(VMTextError):
        await vmtext.type_into_vm(_StubPool(), t, text="caf\u00e9", max_chars=512)


async def test_type_into_vm_rejects_overlong():
    t = Inventory.load(EXAMPLE).by_name("DMZH2_DC")
    with pytest.raises(VMTextError):
        await vmtext.type_into_vm(_StubPool(), t, text="x" * 10, max_chars=5)


def test_type_text_script_escapes_quotes_and_targets_vm_by_name():
    script = _type_text_script(vm_name="My'VM", text="pa'ss")
    assert "My''VM" in script
    assert "pa''ss" in script
    assert "Msvm_Keyboard" in script


async def test_push_and_pull_are_byte_exact():
    pool = _StubPool()
    t = Inventory.load(EXAMPLE).by_name("DMZH1_MSSQL")
    data = b"line1\r\nline2\n\ttabbed\n"
    await vmtext.push_to_vm(pool, t, data=data, remote_path="~/labdrop/x.txt")
    assert await vmtext.pull_from_vm(pool, t, remote_path="~/labdrop/x.txt") == data


def test_default_drop_path_per_os():
    inv = Inventory.load(EXAMPLE)
    win = vmtext.default_drop_path(inv.by_name("DMZH2_DC"), "a.ps1", "C:\\LabDrop", "~/labdrop")
    lin = vmtext.default_drop_path(inv.by_name("L4H1_Attacker_Kali"), "a.sh", "C:\\LabDrop", "~/labdrop")
    assert win == "C:\\LabDrop\\a.ps1"
    assert lin == "~/labdrop/a.sh"


def test_inventory_rejects_unknown_host():
    bad = {
        "hypervisors": [{"name": "H1", "kind": "hypervisor", "os": "windows", "segment": "DMZ"}],
        "targets": [{"name": "G1", "kind": "guest", "os": "windows", "segment": "DMZ", "host": "NOPE"}],
    }
    with pytest.raises(ValueError):
        Inventory.model_validate(bad)


def test_inventory_accepts_network_devices():
    inv = Inventory.model_validate({
        "network": [{"name": "FW1", "kind": "network", "os": "network", "segment": "DMZ",
                     "address": "10.1.20.254", "credential": "fw/admin", "vendor": "fortigate"}],
    })
    fw = inv.by_name("FW1")
    assert fw is not None and fw.configured and fw.vendor == "fortigate"
