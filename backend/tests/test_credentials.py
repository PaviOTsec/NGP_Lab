"""Plaintext credentials file parsing and pool credential classes."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.credentials import CredentialsError, CredentialStore
from app.core.pool import CredClass, SessionPool
from app.models.inventory import Inventory
from app.transports.base import TransportError

GOOD = """
credentials:
  H1/HyperVAdmin:
    username: H1\\HyperVAdmin
    password: "p@ss: with 'quotes'"
  linux/key:
    username: np_admin
    ssh_key: |
      -----BEGIN OPENSSH PRIVATE KEY-----
      abc
      -----END OPENSSH PRIVATE KEY-----
"""


def test_parse_and_lookup():
    store = CredentialStore.parse(GOOD, source="creds.yaml")
    c = store.credential("H1/HyperVAdmin")
    assert c.username == "H1\\HyperVAdmin"
    assert c.password == "p@ss: with 'quotes'"
    assert "BEGIN OPENSSH" in (store.credential("linux/key").ssh_private_key or "")
    assert store.names() == ["H1/HyperVAdmin", "linux/key"]


def test_missing_entry_is_a_transport_error():
    store = CredentialStore.parse(GOOD)
    with pytest.raises(TransportError):
        store.credential("nope")


@pytest.mark.parametrize("bad", ["", "credentials: [1, 2]", "foo: bar", ": : :"])
def test_malformed_files_are_rejected(bad):
    with pytest.raises(CredentialsError):
        CredentialStore.parse(bad)


def test_ssh_key_file_is_read(tmp_path):
    key = tmp_path / "id"
    key.write_text("KEYDATA", encoding="utf-8")
    store = CredentialStore.parse(f"credentials:\n  k:\n    username: u\n    ssh_key_file: '{key}'\n")
    assert store.credential("k").ssh_private_key == "KEYDATA"


def _pool() -> SessionPool:
    inv = Inventory.model_validate({
        "hypervisors": [{"name": "H1", "kind": "hypervisor", "os": "windows", "segment": "DMZ",
                         "address": "10.0.0.1", "credential": "H1/HyperVAdmin"}],
        "targets": [{"name": "APP", "kind": "appliance", "os": "appliance", "segment": "DMZ",
                     "host": "H1", "vm_name": "APP", "access": "power-only"}],
    })
    return SessionPool(settings=Settings(), inventory=inv, creds=CredentialStore.parse(GOOD))


async def test_host_admin_requires_declared_admin_credential():
    """A host-admin step must never quietly fall back to HyperVAdmin."""
    with pytest.raises(TransportError, match="admin_credential"):
        await _pool().shell("H1", CredClass.HOST_ADMIN)


async def test_appliances_never_get_a_shell():
    with pytest.raises(TransportError, match="power-only"):
        await _pool().shell("APP")
