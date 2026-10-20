"""Append-only audit log. Every externally visible action lands here, never a secret.

One JSON object per line. Rotated when it passes `rotate_mb`. Optionally mirrored to Splunk
HEC when configured (the HEC token comes from the credentials file, not from settings).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: Path, rotate_mb: int = 10) -> None:
        self._path = path
        self._rotate_bytes = rotate_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        action: str,
        target: str,
        transport: str = "",
        result: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Write one event. `detail` must already be secret-free."""
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "target": target,
            "transport": transport,
            "result": result,
        }
        if detail:
            event["detail"] = _scrub(detail)
        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            self._maybe_rotate()
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tail(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out: list[dict[str, Any]] = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out

    def _maybe_rotate(self) -> None:
        try:
            if self._path.exists() and self._path.stat().st_size >= self._rotate_bytes:
                stamp = time.strftime("%Y%m%d-%H%M%S")
                self._path.rename(self._path.with_suffix(f".{stamp}.jsonl"))
        except OSError:
            pass


# Keys that must never appear in an audit detail, even by accident.
_FORBIDDEN = {"password", "passphrase", "secret", "private_key", "ssh_private_key", "token"}


def _scrub(detail: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for k, v in detail.items():
        if k.lower() in _FORBIDDEN:
            clean[k] = "<redacted>"
        elif isinstance(v, dict):
            clean[k] = _scrub(v)
        else:
            clean[k] = v
    return clean
