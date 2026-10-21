"""Edit config/inventory.yaml from the console, as text.

Text, not a form: the file's comments carry the observation history (DRIFT notes, pins, dates)
and PyYAML can't round-trip them. The operator edits the YAML; this module validates it with
the same model the loader uses, explains what would change, and writes it with a dated backup.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.models.inventory import Inventory, Target


@dataclass
class Review:
    ok: bool
    errors: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # handle-with-care notes (rule 13)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _errors(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return [str(exc)]


def review(current: Inventory | None, text: str) -> Review:
    """Parse + validate `text` and describe its effect relative to `current`."""
    try:
        new = Inventory.parse(text)
    except Exception as exc:  # noqa: BLE001 - YAML or model errors both go back to the editor
        return Review(ok=False, errors=_errors(exc))
    old = {t.name: t for t in current.all()} if current else {}
    now = {t.name: t for t in new.all()}
    r = Review(
        ok=True,
        added=sorted(now.keys() - old.keys()),
        removed=sorted(old.keys() - now.keys()),
        changed=sorted(n for n in now.keys() & old.keys() if now[n] != old[n]),
    )
    for name in [*r.added, *r.changed]:
        t, before = now[name], old.get(name)
        if not t.ot:
            continue
        if t.configured and not (before and before.configured):
            r.warnings.append(f"{name} (OT) becomes loginable: the console will connect to it on reload")
        if before and _identity(before) != _identity(t):
            r.warnings.append(f"{name} (OT): address or identity pin changed")
    return r


def _identity(t: Target) -> tuple:
    return (t.address, t.hostname, t.ssh_fingerprint, t.vm_name, t.host)


def write(path: Path, text: str, base_sha256: str) -> Path:
    """Write `text` over `path` if it still holds what the editor loaded; return the backup."""
    raw = path.read_bytes()
    if sha256(raw.decode("utf-8")) != base_sha256:
        raise FileExistsError("inventory.yaml changed on disk since it was opened; reload the editor")
    # Keep the file's own line endings (rule 11: never translate them by accident). The browser
    # hands back \n; the file on MC01 may be CRLF.
    body = text.replace("\r\n", "\n")
    if b"\r\n" in raw:
        body = body.replace("\n", "\r\n")
    backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    backup.write_bytes(raw)
    path.write_bytes(body.encode("utf-8"))
    return backup
