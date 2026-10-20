"""Settings loader. Reads config/settings.toml; no credentials here.

Paths may contain %ENV% tokens (e.g. %LOCALAPPDATA%) which are expanded on load so the same
file works regardless of the operator's account.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


def _expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


class ServerSettings(BaseModel):
    """The operator console (full lab control). Loopback by default; widen deliberately."""

    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True


class ClipboardServerSettings(BaseModel):
    """The shared clipboard page, opened from the VMs. Serves ONLY clipboard routes."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8766


class SessionSettings(BaseModel):
    connect_timeout_seconds: int = 5
    reconnect_backoff_seconds: list[int] = Field(default_factory=lambda: [1, 2, 5, 10, 30])
    reachability_poll_seconds: int = 10


class FileSettings(BaseModel):
    windows_drop_dir: str = "C:\\LabDrop"
    linux_drop_dir: str = "~/labdrop"


class AuditSettings(BaseModel):
    path: str = "%LOCALAPPDATA%/LabConsole/audit.jsonl"
    rotate_mb: int = 10
    splunk_hec_url: str = ""
    splunk_hec_credential: str = ""  # credentials-file entry name, if forwarding is enabled


class ClipboardSettings(BaseModel):
    data_dir: str = "%LOCALAPPDATA%/LabConsole/clipboard"
    max_items_per_board: int = 200
    max_file_mb: int = 2048
    # Text items up to this size are sent inline to the page so "Copy" works in one click.
    inline_text_kb: int = 1024
    # Msvm_Keyboard.TypeText is ASCII + US-layout only; cap the length typed in one go.
    type_text_max_chars: int = 512


class PlaybookSettings(BaseModel):
    runs_dir: str = "%LOCALAPPDATA%/LabConsole/runs"
    default_concurrency: int = 8


class Settings(BaseModel):
    server: ServerSettings = Field(default_factory=ServerSettings)
    clipboard_server: ClipboardServerSettings = Field(default_factory=ClipboardServerSettings)
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    clipboard: ClipboardSettings = Field(default_factory=ClipboardSettings)
    playbooks: PlaybookSettings = Field(default_factory=PlaybookSettings)
    # Small non-secret state remembered across launches (e.g. last credentials file path).
    state_path: str = "%LOCALAPPDATA%/LabConsole/state.json"

    # resolved absolute paths (filled on load)
    config_dir: Path = Field(default_factory=lambda: Path.cwd())

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def inventory_path(self) -> Path:
        return self.config_dir / "inventory.yaml"

    @property
    def audit_abs(self) -> Path:
        return Path(_expand(self.audit.path))

    @property
    def clipboard_dir(self) -> Path:
        return Path(_expand(self.clipboard.data_dir))

    @property
    def runs_abs(self) -> Path:
        return Path(_expand(self.playbooks.runs_dir))

    @property
    def state_abs(self) -> Path:
        return Path(_expand(self.state_path))

    @classmethod
    def load(cls, config_dir: str | Path | None = None) -> Settings:
        cfg_dir = Path(config_dir) if config_dir else _default_config_dir()
        settings_file = cfg_dir / "settings.toml"
        data: dict = {}
        if settings_file.exists():
            data = tomllib.loads(settings_file.read_text(encoding="utf-8"))
        obj = cls.model_validate(data)
        obj.config_dir = cfg_dir
        return obj


def _default_config_dir() -> Path:
    """Locate the repo's config/ directory relative to this file, overridable by env."""
    if env := os.environ.get("LABCONSOLE_CONFIG_DIR"):
        return Path(env)
    # backend/app/config.py -> repo root is two parents up from backend/
    return Path(__file__).resolve().parents[2] / "config"
