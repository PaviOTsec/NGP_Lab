"""The shared clipboard: a cl1p.net-style board that every VM can open in a browser.

Items are text or files, stored byte-exact on MC01 with a SHA-256 so what comes out is
provably what went in. Text is never normalised on the way in; conversions (line endings,
sanitising, encoding) happen only on the way out, on request (see app.core.textfmt).

Layout on disk (settings.clipboard.data_dir):
    <board>/index.json     item metadata, newest first
    <board>/<id>.bin       item bytes (text items are UTF-8)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from app.core import textfmt

BOARD_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
DEFAULT_BOARD = "main"


class ClipError(Exception):
    pass


class ClipNotFound(ClipError):
    pass


@dataclass
class ClipItem:
    id: str
    kind: str  # "text" | "file"
    created: str  # ISO-8601
    size: int
    sha256: str
    name: str = ""  # filename (files) or optional label (text)
    eol: str = ""  # text: crlf | lf | mixed | none
    suspicious: int = 0  # text: chars that `sanitize` would change
    lines: int = 0  # text: line count
    origin: str = ""  # client address that added it

    def to_dict(self) -> dict:
        return asdict(self)


class ClipStore:
    def __init__(self, root: Path, *, max_items: int = 200, max_file_bytes: int = 2 << 30) -> None:
        self.root = root
        self.max_items = max_items
        self.max_file_bytes = max_file_bytes
        self._lock = threading.Lock()
        # Version counters let pages poll cheaply. Seeded from the clock so a restart never
        # hands a client the same version number for different contents.
        self._versions: dict[str, int] = {}
        self._seed = int(time.time() * 1000)
        root.mkdir(parents=True, exist_ok=True)

    # --- boards ---

    def _board_dir(self, board: str) -> Path:
        if not BOARD_RE.match(board):
            raise ClipError("board names are 1-40 chars of letters, digits, . _ -")
        return self.root / board

    def version(self, board: str) -> int:
        self._board_dir(board)
        return self._versions.get(board, self._seed)

    def _bump(self, board: str) -> None:
        self._versions[board] = max(self._versions.get(board, self._seed) + 1,
                                    int(time.time() * 1000))

    def boards(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and BOARD_RE.match(p.name))

    # --- index ---

    def _read_index(self, board: str) -> list[ClipItem]:
        path = self._board_dir(board) / "index.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [ClipItem(**r) for r in raw]

    def _write_index(self, board: str, items: list[ClipItem]) -> None:
        d = self._board_dir(board)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "index.json.tmp"
        tmp.write_text(json.dumps([i.to_dict() for i in items], indent=1), encoding="utf-8")
        os.replace(tmp, d / "index.json")

    def list(self, board: str) -> list[ClipItem]:
        with self._lock:
            return self._read_index(board)

    def get(self, board: str, item_id: str) -> ClipItem:
        for item in self.list(board):
            if item.id == item_id:
                return item
        raise ClipNotFound(f"no item {item_id!r} on board {board!r}")

    def latest(self, board: str, kind: str | None = None) -> ClipItem:
        for item in self.list(board):
            if kind is None or item.kind == kind:
                return item
        raise ClipNotFound(f"board {board!r} has no {kind or 'items'}")

    def blob_path(self, board: str, item_id: str) -> Path:
        self.get(board, item_id)  # existence check
        return self._board_dir(board) / f"{item_id}.bin"

    def read_bytes(self, board: str, item_id: str) -> bytes:
        return self.blob_path(board, item_id).read_bytes()

    def read_text(self, board: str, item_id: str) -> str:
        return self.read_bytes(board, item_id).decode("utf-8", errors="replace")

    # --- adding ---

    def add_text(self, board: str, text: str, *, origin: str = "", name: str = "") -> ClipItem:
        data = text.encode("utf-8")
        item = ClipItem(
            id="", kind="text", created=_now(), size=len(data),
            sha256=hashlib.sha256(data).hexdigest(), name=_clean_name(name),
            eol=textfmt.detect_eol(text), suspicious=textfmt.suspicious_chars(text),
            lines=text.count("\n") + (1 if text and not text.endswith("\n") else 0),
            origin=origin,
        )
        return self._commit(board, item, lambda f: f.write(data))

    def add_file(self, board: str, filename: str, src: BinaryIO, *, origin: str = "") -> ClipItem:
        """Stream a file in, hashing as it goes. Enforces max_file_bytes."""
        digest = hashlib.sha256()
        size = 0

        def write(f: BinaryIO) -> None:
            nonlocal size
            while chunk := src.read(1024 * 1024):
                size += len(chunk)
                if size > self.max_file_bytes:
                    raise ClipError(f"file exceeds the {self.max_file_bytes >> 20} MB limit")
                digest.update(chunk)
                f.write(chunk)

        item = ClipItem(id="", kind="file", created=_now(), size=0, sha256="",
                        name=_clean_name(filename) or "file", origin=origin)

        def finish(it: ClipItem) -> None:
            it.size, it.sha256 = size, digest.hexdigest()

        return self._commit(board, item, write, finish)

    def _commit(self, board: str, item: ClipItem, write, finish=None) -> ClipItem:
        d = self._board_dir(board)
        d.mkdir(parents=True, exist_ok=True)
        item.id = self._new_id(board)
        tmp = d / f"{item.id}.part"
        try:
            with tmp.open("wb") as f:
                write(f)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        if finish:
            finish(item)
        os.replace(tmp, d / f"{item.id}.bin")
        with self._lock:
            items = [item, *self._read_index(board)]
            for old in items[self.max_items:]:
                (d / f"{old.id}.bin").unlink(missing_ok=True)
            self._write_index(board, items[: self.max_items])
            self._bump(board)
        return item

    def _new_id(self, board: str) -> str:
        existing = {i.id for i in self.list(board)}
        while True:
            candidate = secrets.token_hex(3)  # 6 hex chars: short enough to type in a VM
            if candidate not in existing:
                return candidate

    # --- removing ---

    def delete(self, board: str, item_id: str) -> None:
        with self._lock:
            items = self._read_index(board)
            kept = [i for i in items if i.id != item_id]
            if len(kept) == len(items):
                raise ClipNotFound(f"no item {item_id!r} on board {board!r}")
            (self._board_dir(board) / f"{item_id}.bin").unlink(missing_ok=True)
            self._write_index(board, kept)
            self._bump(board)

    def clear(self, board: str) -> None:
        with self._lock:
            d = self._board_dir(board)
            for item in self._read_index(board):
                (d / f"{item.id}.bin").unlink(missing_ok=True)
            self._write_index(board, [])
            self._bump(board)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _clean_name(name: str) -> str:
    """Display/download name only (storage uses the id): basename, no control/path chars."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip(" .")
    return name[:200]
