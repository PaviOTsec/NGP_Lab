"""Plaintext credentials file, chosen by the operator from the app at startup.

Replaces the earlier KeePass vault. The file is YAML (format in
config/credentials.example.yaml); the inventory refers to entries by name. The parsed store
lives in backend memory; the file itself stays wherever the operator keeps it.

    credentials:
      DMZ-HOST-1/HyperVAdmin:
        username: DMZ-HOST-1\\HyperVAdmin
        password: "..."
      sinecins/np_admin:
        username: np_admin
        password: "..."            # optional when a key is given
        ssh_key_file: C:\\lab\\keys\\sinecins_ed25519   # or inline `ssh_key: |`
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.transports.base import Credential, TransportError


class CredentialsError(TransportError):
    """The credentials file is missing, malformed, or lacks an entry.

    A TransportError subclass so a missing entry fails one target the same way an
    unreachable host does, without special-casing it at every call site.
    """


class CredentialStore:
    def __init__(self, entries: dict[str, Credential], source: str = "") -> None:
        self._entries = entries
        self.source = source  # file name/path it was loaded from, for display only

    @classmethod
    def parse(cls, text: str, source: str = "") -> CredentialStore:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise CredentialsError(f"credentials file is not valid YAML: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("credentials"), dict):
            raise CredentialsError("credentials file must have a top-level `credentials:` mapping")

        entries: dict[str, Credential] = {}
        for name, raw in data["credentials"].items():
            if not isinstance(raw, dict):
                raise CredentialsError(f"entry {name!r} must be a mapping")
            key = raw.get("ssh_key")
            if key_file := raw.get("ssh_key_file"):
                try:
                    key = Path(key_file).expanduser().read_text(encoding="utf-8")
                except OSError as exc:
                    raise CredentialsError(f"entry {name!r}: cannot read ssh_key_file") from exc
            entries[str(name)] = Credential(
                username=str(raw.get("username", "")),
                password=None if raw.get("password") is None else str(raw["password"]),
                ssh_private_key=key,
                source_entry=str(name),
            )
        return cls(entries, source)

    @classmethod
    def load(cls, path: str | Path) -> CredentialStore:
        p = Path(path).expanduser()
        try:
            text = p.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise CredentialsError(f"cannot read credentials file: {p}") from exc
        return cls.parse(text, source=str(p))

    def credential(self, name: str) -> Credential:
        if not name:
            raise CredentialsError("target has no credential configured")
        try:
            return self._entries[name]
        except KeyError:
            raise CredentialsError(f"credential not found: {name!r}") from None

    def names(self) -> list[str]:
        return sorted(self._entries)
