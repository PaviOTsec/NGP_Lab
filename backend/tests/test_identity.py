"""Identity pins: credentials are never sent to a machine that isn't the one in the inventory."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.config import Settings
from app.core import identity
from app.core.credentials import CredentialStore
from app.core.identity import HostIdentity, IdentityMismatch, parse_challenge
from app.core.pool import SessionPool
from app.models.inventory import Inventory, Segment
from app.transports.base import TransportError

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "inventory.example.yaml"


def _challenge(computer: str, domain: str, dns_computer: str = "", dns_domain: str = "") -> bytes:
    """A minimal NTLM CHALLENGE (type 2) message carrying target-info AV pairs."""
    def av(av_id: int, value: str) -> bytes:
        raw = value.encode("utf-16-le")
        return struct.pack("<HH", av_id, len(raw)) + raw

    info = av(2, domain) + av(1, computer)
    if dns_domain:
        info += av(4, dns_domain)
    if dns_computer:
        info += av(3, dns_computer)
    info += struct.pack("<HH", 0, 0)
    header_len = 56
    msg = b"NTLMSSP\x00" + struct.pack("<I", 2)
    msg += struct.pack("<HHI", 0, 0, header_len)  # target name (empty)
    msg += struct.pack("<I", 0xE2898215)  # flags
    msg += b"\x11" * 8 + b"\x00" * 8  # challenge + reserved
    msg += struct.pack("<HHI", len(info), len(info), header_len)  # target info
    msg += b"\x06\x01\xb1\x1d\x00\x00\x00\x0f"  # version
    return msg + info


def test_parse_workgroup_and_domain_hosts():
    wg = parse_challenge(_challenge("DMZ-HOST-2", "DMZ-HOST-2", "DMZ-HOST-2"))
    assert wg.computer == "DMZ-HOST-2" and not wg.domain_joined
    dj = parse_challenge(_challenge("WSUS", "NP", "WSUS.np.local", "np.local"))
    assert dj.computer == "WSUS" and dj.domain_joined and dj.dns_domain == "np.local"


def test_check_accepts_netbios_or_dns_short_name_case_insensitively():
    identity.check("dmzh2maint", HostIdentity("DMZH2MAINT", "NP", "DMZH2Maint.np.local"), "x")
    identity.check("DMZH2Maint", HostIdentity("", "", "DMZH2Maint.np.local"), "x")


def test_the_real_incident_is_refused():
    """2026-10-09: the drawing's DMZ-HOST-2 address answered as L2-HOST-1."""
    with pytest.raises(IdentityMismatch, match="L2-HOST-1.*expects DMZ-HOST-2.*No credentials"):
        identity.check("DMZ-HOST-2", HostIdentity("L2-HOST-1", "L2-HOST-1"), "192.168.100.13")


def _pool() -> SessionPool:
    inv = Inventory.model_validate({
        "hypervisors": [{"name": "H1", "kind": "hypervisor", "os": "windows", "segment": "DMZ",
                         "address": "10.0.0.1", "credential": "c"}],
        "targets": [{"name": "G1", "kind": "guest", "os": "windows", "segment": "DMZ",
                     "host": "H1", "vm_name": "G1", "address": "10.0.0.2", "credential": "c",
                     "hostname": "GUEST1"}],
    })
    creds = CredentialStore.parse("credentials:\n  c: { username: u, password: p }\n")
    return SessionPool(settings=Settings(), inventory=inv, creds=creds)


async def test_pool_refuses_winrm_login_to_wrong_host(monkeypatch):
    async def wrong(address, timeout=5.0):  # noqa: ARG001
        return HostIdentity("L2-HOST-1", "L2-HOST-1")

    built = []
    monkeypatch.setattr(identity, "probe_identity", wrong)
    monkeypatch.setattr("app.core.pool.WinRMTransport", lambda **kw: built.append(kw))
    with pytest.raises(TransportError, match="identity mismatch"):
        await _pool().shell("H1")
    assert built == []  # the transport (and so the credential) was never even constructed


async def test_guest_mismatch_falls_through_to_powershell_direct(monkeypatch):
    """Direct link refused on identity -> Hyper-V link via the (verified) host is used."""
    async def probe(address, timeout=5.0):  # noqa: ARG001
        return HostIdentity("H1", "H1") if address == "10.0.0.1" else HostIdentity("SOMEONE-ELSE", "X")

    from tests.mocks import result

    class FakeWinRM:
        def __init__(self, **kw):
            self.name, self.connected = "winrm", False

        async def connect(self):
            self.connected = True

        async def run(self, command, timeout=120):  # noqa: ARG002
            if "Get-VM" in command:
                return result("Running")
            return result("GUEST1")  # PowerShell Direct probe: the guest's computer name

    monkeypatch.setattr(identity, "probe_identity", probe)
    monkeypatch.setattr("app.core.pool.WinRMTransport", FakeWinRM)
    t = await _pool().shell("G1")
    assert t.name == "psdirect"


async def test_ssh_host_key_pin_mismatch_sends_nothing(monkeypatch):
    import asyncssh

    from app.transports.base import Credential
    from app.transports.ssh import SSHTransport

    class Key:
        def get_fingerprint(self):
            return "SHA256:imposter"

    async def fake_key(host, port=22):  # noqa: ARG001
        return Key()

    async def must_not_connect(**kw):
        raise AssertionError("authenticated despite a host-key mismatch")

    monkeypatch.setattr(asyncssh, "get_server_host_key", fake_key)
    monkeypatch.setattr(asyncssh, "connect", must_not_connect)
    t = SSHTransport(target_name="SW", address="10.0.0.9", credential=Credential("admin", "x"),
                     expected_fingerprint="SHA256:pinned")
    with pytest.raises(TransportError, match="host key mismatch"):
        await t.connect()


async def test_psdirect_refuses_off_vm_and_wrong_guest():
    from app.transports.base import Credential, Unreachable
    from app.transports.psdirect import PSDirectTransport
    from tests.mocks import make, result

    off = make("H", responses=[("Get-VM", result("Off"))])
    t = PSDirectTransport(target_name="EPO", address="EPO", credential=Credential("u", "p"),
                          host_transport=off, vm_name="EPO")
    with pytest.raises(Unreachable, match="is Off"):
        await t.connect()

    wrong = make("H", responses=[("Get-VM", result("Running")), ("Invoke-Command", result("OTHER"))])
    t = PSDirectTransport(target_name="G", address="G", credential=Credential("u", "p"),
                          host_transport=wrong, vm_name="G", expected_hostname="GUEST1")
    with pytest.raises(TransportError, match="expects GUEST1"):
        await t.connect()


def test_observed_inventory_stays_out_of_l2_and_below():
    """Safety scope: nothing at L2/Plantbus, and none of the known L2 addresses."""
    inv = Inventory.load(EXAMPLE)
    l2_addresses = {"192.168.100.13", "192.168.100.15"}
    for t in inv.all():
        assert t.segment not in (Segment.L2, Segment.PLANTBUS), t.name
        assert t.address not in l2_addresses, t.name
        assert not t.address.startswith(("192.168.20.", "192.168.21.", "192.168.1.",
                                         "192.168.2.", "192.168.3.", "192.168.4.")), t.name
