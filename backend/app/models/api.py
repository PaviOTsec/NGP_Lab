"""Pydantic models for the HTTP/WebSocket API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.inventory import OS, Access, Route, Segment, TargetKind


class TransportName(StrEnum):
    WINRM = "winrm"
    SSH = "ssh"
    SMB = "smb"
    PSDIRECT = "psdirect"
    NONE = "none"


class ConnState(StrEnum):
    PENDING = "pending"
    CONNECTING = "connecting"
    OPEN = "open"
    FAILED = "failed"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class Reachability(BaseModel):
    """Per-transport TCP reachability for a target's dashboard chips."""

    winrm: bool | None = None  # 5985
    ssh: bool | None = None  # 22
    smb: bool | None = None  # 445
    rdp: bool | None = None  # 3389
    https: bool | None = None  # 443


class SessionStatus(BaseModel):
    target: str
    transport: TransportName
    state: ConnState
    detail: str = ""  # human-readable, secret-free (e.g. "NTLM auth failed")


class CheckpointInfo(BaseModel):
    name: str
    snapshot_type: str  # as read back from Get-VMSnapshot (Production / Standard)
    created_at: str | None = None


class TargetView(BaseModel):
    """Everything the dashboard shows for one target — inventory merged with live discovery."""

    name: str
    kind: TargetKind
    os: OS
    segment: Segment
    address: str
    route: Route
    access: Access
    configured: bool
    web_ui: str | None = None
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    ot: bool = False  # L2 and below: the UI handles it with care

    # live, from discovery (None until discovered)
    power_state: str | None = None  # Running / Off / Saved / Paused
    uptime_seconds: int | None = None
    guest_ips: list[str] = Field(default_factory=list)
    checkpoints: list[CheckpointInfo] = Field(default_factory=list)
    reachability: Reachability = Field(default_factory=Reachability)
    session: SessionStatus | None = None


class FanoutRequest(BaseModel):
    targets: list[str]
    command: str
    # "auto" lets the pool choose per target; or force "powershell" / "bash"
    shell: str = "auto"
    timeout_seconds: int = 120


class FanoutResult(BaseModel):
    target: str
    transport: TransportName
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    error: str | None = None


class CheckpointRequest(BaseModel):
    target: str
    checkpoint_type: str = "Production"  # Production | Standard
    name: str | None = None


class HyperVActionRequest(BaseModel):
    target: str
    action: str  # start | shutdown | turnoff | save | checkpoint | restore | delete-checkpoint
    checkpoint_name: str | None = None


class GroupRestoreRequest(BaseModel):
    targets: list[str]
    checkpoint_name: str
