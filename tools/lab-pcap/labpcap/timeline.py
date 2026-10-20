"""Collects frames from every flow on one relative timeline and writes the capture."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import pcapng


class Timeline:
    def __init__(self, duration_s: float) -> None:
        self.duration = duration_s
        self.frames: list[tuple[float, int, bytes]] = []
        self._n = 0

    def add(self, t: float, frame: bytes) -> None:
        if 0.0 <= t < self.duration:
            self.frames.append((t, self._n, frame))   # _n keeps same-time frames in emission order
            self._n += 1

    def write(self, path: Path, start_epoch: float, if_name: str) -> str:
        self.frames.sort(key=lambda f: (f[0], f[1]))
        out = [(start_epoch + t, fr) for t, _, fr in self.frames]
        path.parent.mkdir(parents=True, exist_ok=True)
        pcapng.write(path, out, if_name=if_name)
        return hashlib.sha256(path.read_bytes()).hexdigest()
