"""Playbook schema.

A playbook is one YAML file in `playbooks/` (user) or `app/playbooks/builtin/` (shipped):

    name: host-health                 # id; defaults to the file name
    title: Host health snapshot
    description: Disk free, WinRM start type, local time.
    targets:                          # which inventory targets it runs on (all keys AND-ed)
      kind: hypervisor                #   hypervisor | guest | appliance | network
      os: windows                     #   windows | linux | appliance | network
      segment: DMZ
      vendor: fortigate
      tags: [backup]                  #   target must carry every listed tag
      names: [DMZ-HOST-1]             #   explicit list
      include_ot: false               #   L2/L1 targets match only if named, segment-selected, or this
    params:
      - { name: delay_ms, type: int, default: 60000, label: "Restart delay (ms)" }
    confirm: true                     # UI asks before running
    concurrency: 8                    # targets in parallel
    steps:
      - name: Disk free
        run: |                        # module name as the key; its value is the module args
          Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'
        register: disk                # keep the result as {{ vars.disk.stdout }}
        credential: default           # default | host-admin
        when: { os: windows }         # skip unless the target matches
        ignore_errors: false
        timeout: 120

Every key on a step that isn't one of the common keys above must be exactly one registered
module name (see app.playbooks.modules). Unknown modules fail at load, not at run time.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.inventory import Target

COMMON_STEP_KEYS = {"name", "register", "credential", "when", "ignore_errors", "timeout"}


class Param(BaseModel):
    name: str
    type: str = "string"  # string | int | bool | choice | text
    default: Any = None
    label: str | None = None
    choices: list[str] = Field(default_factory=list)
    required: bool = False

    def coerce(self, value: Any) -> Any:
        if value is None or value == "":
            if self.required and self.default is None:
                raise ValueError(f"parameter {self.name!r} is required")
            return self.default
        if self.type == "int":
            return int(value)
        if self.type == "bool":
            return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
        if self.type == "choice" and self.choices and str(value) not in self.choices:
            raise ValueError(f"parameter {self.name!r} must be one of {self.choices}")
        return str(value)


class TargetSelector(BaseModel):
    kind: str | None = None
    os: str | None = None
    segment: str | None = None
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    include_ot: bool = False

    def matches(self, t: Target) -> bool:
        if self.names and t.name not in self.names:
            return False
        # Handle with care: a broad selector ("every guest") never sweeps in L2/L1 by accident.
        if t.ot and not (self.include_ot or self.names or self.segment):
            return False
        if self.kind and t.kind.value != self.kind:
            return False
        if self.os and t.os.value != self.os:
            return False
        if self.segment and t.segment.value != self.segment:
            return False
        if self.vendor and (t.vendor or "") != self.vendor:
            return False
        if self.tags and not set(self.tags).issubset(t.tags):
            return False
        return True


class Step(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = ""
    module: str
    args: Any = None
    register_as: str | None = Field(default=None, alias="register")
    credential: str = "default"
    when: dict[str, Any] = Field(default_factory=dict)
    ignore_errors: bool = False
    timeout: int = 300

    @classmethod
    def from_raw(cls, raw: dict[str, Any], known_modules: set[str]) -> Step:
        if not isinstance(raw, dict):
            raise ValueError("each step must be a mapping")
        module_keys = [k for k in raw if k not in COMMON_STEP_KEYS]
        if len(module_keys) != 1:
            raise ValueError(
                f"step {raw.get('name', '?')!r} must name exactly one module, found {module_keys}"
            )
        module = module_keys[0]
        if module not in known_modules:
            raise ValueError(f"unknown module {module!r} (known: {sorted(known_modules)})")
        common = {k: v for k, v in raw.items() if k in COMMON_STEP_KEYS}
        return cls(module=module, args=raw[module], **common)

    def applies_to(self, t: Target) -> bool:
        for key, want in self.when.items():
            have = getattr(t, key, None)
            have = getattr(have, "value", have)
            if isinstance(want, list):
                if have not in want and not (isinstance(have, list) and set(want) & set(have)):
                    return False
            elif isinstance(have, list):
                if want not in have:
                    return False
            elif have != want:
                return False
        return True


class Playbook(BaseModel):
    name: str
    title: str = ""
    description: str = ""
    targets: TargetSelector = Field(default_factory=TargetSelector)
    params: list[Param] = Field(default_factory=list)
    confirm: bool = False
    concurrency: int | None = None
    steps: list[Step]
    source_file: str = ""

    @model_validator(mode="after")
    def _defaults(self) -> Playbook:
        if not self.title:
            self.title = self.name
        if not self.steps:
            raise ValueError("a playbook needs at least one step")
        return self

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any], *, default_name: str, source_file: str,
                       known_modules: set[str]) -> Playbook:
        if not isinstance(data, dict):
            raise ValueError("playbook file must be a mapping")
        data = dict(data)
        raw_steps = data.pop("steps", None) or []
        steps = [Step.from_raw(s, known_modules) for s in raw_steps]
        for i, s in enumerate(steps, 1):
            s.name = s.name or f"{s.module} #{i}"
        data.setdefault("name", default_name)
        return cls(steps=steps, source_file=source_file, **data)

    def resolve_params(self, values: dict[str, Any]) -> dict[str, Any]:
        return {p.name: p.coerce(values.get(p.name)) for p in self.params}
