"""In-app inventory editor: validate, describe the change, write with backup + same line endings."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import inventory_edit
from app.models.inventory import Inventory

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "inventory.example.yaml"


def test_review_reports_yaml_and_model_errors():
    assert not inventory_edit.review(None, "hypervisors: [").ok
    bad = inventory_edit.review(None, "targets:\n  - {name: X, kind: guest, os: windows, segment: NOPE}\n")
    assert not bad.ok and any("segment" in e for e in bad.errors)


def test_review_describes_changes_and_warns_on_ot():
    text = EXAMPLE.read_text(encoding="utf-8")
    current = Inventory.parse(text)
    edited = text.replace(
        "    vm_name: OSS01\n    hostname: OSS01\n",
        "    vm_name: OSS01\n    hostname: OSS01\n    credential: np.local/Administrator\n",
    ).replace("address: 10.1.20.14", "address: 10.1.20.99")
    r = inventory_edit.review(current, edited)
    assert r.ok and r.changed == ["DMZH1_MSSQL", "L2H1_OSS01"] and not r.added and not r.removed
    assert any("L2H1_OSS01" in w and "loginable" in w for w in r.warnings)
    assert not any("DMZH1_MSSQL" in w for w in r.warnings)  # not OT


def test_ot_network_device_needs_a_pin():
    sw = {"name": "S", "kind": "network", "os": "network", "segment": "L1",
          "address": "192.168.1.30", "credential": "network/admin"}
    with pytest.raises(ValueError, match="ssh_fingerprint"):
        Inventory.model_validate({"network": [sw]})
    Inventory.model_validate({"network": [{**sw, "ssh_fingerprint": "SHA256:x"}]})


def test_routes_validate_save_and_reload(tmp_path: Path):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.audit import AuditLog
    from app.deps import require_ready, verify_token
    from app.routes import inventory as inv_routes

    inv_path = tmp_path / "inventory.yaml"
    inv_path.write_bytes(EXAMPLE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    reloads: list[int] = []

    class Session(SimpleNamespace):
        async def load_credentials(self, store):
            self.inventory = Inventory.load(inv_path)
            reloads.append(1)

        async def warm_up(self):
            return []

    s = Session(settings=SimpleNamespace(inventory_path=inv_path), inventory=Inventory.load(inv_path),
                audit=AuditLog(tmp_path / "audit.jsonl"), credentials=object())
    app = FastAPI()
    app.include_router(inv_routes.router)
    app.dependency_overrides[verify_token] = lambda: None
    app.dependency_overrides[require_ready] = lambda: s
    c = TestClient(app)

    src = c.get("/api/inventory/source").json()
    assert "\r\n" in src["text"]  # raw, untranslated
    edited = src["text"].replace("\r\n", "\n").replace("address: 10.1.20.14", "address: 10.1.20.99")
    assert c.post("/api/inventory/validate", json={"text": "targets: ["}).json()["ok"] is False
    assert c.put("/api/inventory/source", json={"text": edited, "base_sha256": "stale"}).status_code == 409
    r = c.put("/api/inventory/source", json={"text": edited, "base_sha256": src["sha256"]})
    assert r.status_code == 200 and r.json()["changed"] == ["DMZH1_MSSQL"] and reloads == [1]
    assert b"address: 10.1.20.99\r\n" in inv_path.read_bytes()
    assert s.inventory.by_name("DMZH1_MSSQL").address == "10.1.20.99"
    assert len(list(tmp_path.glob("inventory.yaml.bak-*"))) == 1
    assert "inventory-edit" in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_write_keeps_crlf_backs_up_and_refuses_stale_edits(tmp_path: Path):
    p = tmp_path / "inventory.yaml"
    p.write_bytes(b"# c\r\nhypervisors: []\r\n")
    base = inventory_edit.sha256(p.read_bytes().decode("utf-8"))
    backup = inventory_edit.write(p, "# c\nhypervisors: []\ntargets: []\n", base)
    assert p.read_bytes() == b"# c\r\nhypervisors: []\r\ntargets: []\r\n"
    assert backup.read_bytes() == b"# c\r\nhypervisors: []\r\n"
    with pytest.raises(FileExistsError):
        inventory_edit.write(p, "x: 1\n", base)  # file moved on since `base`
