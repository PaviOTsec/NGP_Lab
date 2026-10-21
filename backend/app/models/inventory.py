"""Inventory model — what the console manages. Loaded from config/inventory.yaml.

Holds no secrets: each target references a credentials-file entry by name; the file is chosen in the
app at startup.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class TargetKind(StrEnum):
    HYPERVISOR = "hypervisor"
    GUEST = "guest"
    APPLIANCE = "appliance"
    NETWORK = "network"  # switches/firewalls (SCALANCE, FortiGate, Palo Alto), reached over SSH
    BAREMETAL = "baremetal"  # physical machine: no hypervisor, so no power/checkpoint actions
    FIELD = "field"  # L1 controller / IED / RTU / IO: shown on the dashboard, never probed or logged into


class OS(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    APPLIANCE = "appliance"
    NETWORK = "network"  # vendor CLI over SSH; `vendor` says which dialect


class Segment(StrEnum):
    """Purdue-style zones, top to bottom (drawing NP-ARCH-001). L2 and below are in scope but
    handled with care (CLAUDE.md rule 13): see `Target.ot`."""

    L5 = "L5"  # WAN 10.5.20.0/24
    L4 = "L4"  # Enterprise 10.4.20.0/24
    DMZ = "DMZ"  # 10.1.20.0/24
    L3 = "L3"  # Ops Mgmt 192.168.30.0/24
    PLANTBUS = "Plantbus"
    L2 = "L2"  # System 192.168.20.0/24, Terminal 192.168.21.0/24
    L1 = "L1"  # control cells: PCS 192.168.1, SIS .2, SAS .3, power generation .4
    MGMT = "Mgmt"  # Host management 192.168.100.0/24


OT_SEGMENTS = frozenset({Segment.PLANTBUS, Segment.L2, Segment.L1})


class Access(StrEnum):
    """Ceiling of what the console may do on a target."""

    FULL = "full"
    SSH_WEB = "ssh-web"
    POWER_ONLY = "power-only"


class Route(StrEnum):
    """How the console reaches a target. Drives transport selection and the v2 hardening path."""

    DIRECT = "direct"
    VIA_HOST = "via-host"
    VIA_JUMP = "via-jump"


class Target(BaseModel):
    name: str
    kind: TargetKind
    os: OS
    segment: Segment
    address: str = ""
    host: str | None = None  # name of the hypervisor running this VM (for guests/appliances)
    vm_name: str | None = None  # VM name on its hypervisor
    user: str | None = None  # SSH login user (linux)
    credential: str = ""  # credentials-file entry name
    admin_credential: str | None = None  # separate host-admin entry for declared host-level actions
    route: Route = Route.DIRECT
    access: Access = Access.FULL
    web_ui: str | None = None
    vendor: str | None = None  # network devices: scalance | fortigate | paloalto | ...
    # Identity pins, checked BEFORE any credential is sent (app.core.identity):
    hostname: str | None = None  # Windows NetBIOS name; defaults to `name`
    ssh_fingerprint: str | None = None  # SSH host key, e.g. "SHA256:..."
    tags: list[str] = Field(default_factory=list)

    @property
    def expected_hostname(self) -> str:
        return self.hostname or self.name

    @property
    def configured(self) -> bool:
        """A target is usable only once its address (or a via-host route) and credential are known."""
        if self.kind == TargetKind.FIELD:
            return False  # display only
        if self.kind == TargetKind.APPLIANCE:
            return bool(self.host)  # appliances are reached via their hypervisor + web UI
        if self.kind == TargetKind.BAREMETAL and self.os == OS.APPLIANCE:
            return bool(self.address)  # web UI only
        if self.access == Access.POWER_ONLY:
            return bool(self.host and self.vm_name)
        has_path = bool(self.address) or (self.route == Route.VIA_HOST and self.host)
        return has_path and bool(self.credential)

    @property
    def is_hypervisor(self) -> bool:
        return self.kind == TargetKind.HYPERVISOR

    @property
    def ot(self) -> bool:
        """L2 and below: handle with care (stronger confirms, no checkpoints, skipped by broad
        playbook selectors unless asked for)."""
        return self.segment in OT_SEGMENTS


class Inventory(BaseModel):
    hypervisors: list[Target] = Field(default_factory=list)
    targets: list[Target] = Field(default_factory=list)
    network: list[Target] = Field(default_factory=list)
    baremetal: list[Target] = Field(default_factory=list)
    field: list[Target] = Field(default_factory=list)  # L1 controllers/IEDs/RTU: display only

    @model_validator(mode="after")
    def _check_unique_names(self) -> Inventory:
        names = [t.name for t in self.all()]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate target names in inventory: {sorted(dupes)}")
        # Every guest/appliance must point at a real hypervisor.
        hv_names = {h.name for h in self.hypervisors}
        for t in self.targets:
            if t.host and t.host not in hv_names:
                raise ValueError(f"target {t.name!r} references unknown host {t.host!r}")
        # Field devices are hands-off: no credential, so nothing can ever log into one.
        field_names = {t.name for t in self.field}
        for t in self.all():
            if (t.kind == TargetKind.FIELD) != (t.name in field_names):
                raise ValueError(f"{t.name!r}: kind 'field' belongs in (and only in) the field: section")
            if t.kind == TargetKind.FIELD and (t.credential or t.admin_credential):
                raise ValueError(f"field device {t.name!r} must not carry a credential")
            # Rule 12 + 13: an OT network device is never logged into without a host-key pin.
            if t.ot and t.os == OS.NETWORK and t.credential and not t.ssh_fingerprint:
                raise ValueError(f"OT network device {t.name!r} has a credential but no ssh_fingerprint pin")
        return self

    def all(self) -> list[Target]:
        return [*self.hypervisors, *self.targets, *self.baremetal, *self.network, *self.field]

    def by_name(self, name: str) -> Target | None:
        return next((t for t in self.all() if t.name == name), None)

    def hypervisor_for(self, target: Target) -> Target | None:
        if target.is_hypervisor:
            return target
        if not target.host:
            return None
        return next((h for h in self.hypervisors if h.name == target.host), None)

    @classmethod
    def load(cls, path: str | Path) -> Inventory:
        return cls.parse(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse(cls, text: str) -> Inventory:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("inventory must be a YAML mapping")
        # tolerate the inventory file carrying advisory keys like `credentials_hint`
        data.pop("credentials_hint", None)
        return cls.model_validate(data)
