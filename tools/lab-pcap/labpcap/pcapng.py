"""Minimal deterministic pcapng writer (one Ethernet interface, microsecond timestamps)."""
from __future__ import annotations

import struct
from pathlib import Path


def _pad4(b: bytes) -> bytes:
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def _opt(code: int, value: bytes) -> bytes:
    return struct.pack("<HH", code, len(value)) + _pad4(value)


def _block(btype: int, body: bytes) -> bytes:
    total = 12 + len(body)
    return struct.pack("<II", btype, total) + body + struct.pack("<I", total)


def write(path: str | Path, frames: list[tuple[float, bytes]], if_name: str, hardware: str = "") -> None:
    """frames: (epoch_seconds, frame_bytes), already sorted."""
    shb_opts = b""
    if hardware:
        shb_opts += _opt(2, hardware.encode())          # shb_hardware
    shb_opts += _opt(0, b"")
    shb = _block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1) + shb_opts)
    idb_opts = _opt(2, if_name.encode()) + _opt(9, bytes([6])) + _opt(0, b"")   # if_name, if_tsresol=10^-6
    idb = _block(0x00000001, struct.pack("<HHI", 1, 0, 262144) + idb_opts)
    with open(path, "wb") as f:
        f.write(shb)
        f.write(idb)
        for ts, data in frames:
            us = int(round(ts * 1_000_000))
            body = struct.pack("<IIIII", 0, us >> 32, us & 0xFFFFFFFF, len(data), len(data)) + _pad4(data)
            f.write(_block(0x00000006, body))
