"""Capture loopback traffic with dumpcap, then reassemble TCP payloads.

Fallback for protocols where a transparent TCP proxy breaks the connect sequence
(libiec61850 is one example: it rejects even a short-latency relay).

Flow: start dumpcap on \\Device\\NPF_Loopback, run the client against the server, stop
dumpcap, parse the captured file into ordered (direction, bytes) chunks per connection.
"""
from __future__ import annotations

import struct
import subprocess
import time
from collections import defaultdict
from pathlib import Path

DUMPCAP = r"C:\Program Files\Wireshark\dumpcap.exe"
LOOPBACK_IFACE = r"\Device\NPF_Loopback"


class LoopbackCapture:
    """Record a block of loopback traffic to a temp pcap, then parse it."""

    def __init__(self, out: Path) -> None:
        self.out = Path(out)
        self._proc: subprocess.Popen | None = None

    def __enter__(self) -> "LoopbackCapture":
        if self.out.exists():
            self.out.unlink()
        # dumpcap takes just filename and interface; no filter (filter arg quoting is painful)
        self._proc = subprocess.Popen(
            [DUMPCAP, "-i", LOOPBACK_IFACE, "-w", str(self.out), "-q", "-N", "100000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Wait for dumpcap to initialize the capture
        for _ in range(60):
            if self.out.exists() and self.out.stat().st_size > 24:
                break
            time.sleep(0.05)
        time.sleep(0.2)
        return self

    def __exit__(self, *exc) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        time.sleep(0.3)


def extract_tcp(pcap: Path, server_port: int) -> list[tuple[str, bytes]]:
    """Reassemble TCP for the one connection to 127.0.0.1:server_port.

    Returns application-layer chunks in arrival order as [(direction, bytes), ...].
    direction = 'c2s' when src_port != server_port, 's2c' otherwise.
    """
    data = pcap.read_bytes()
    # Parse pcapng; we only need Enhanced Packet Blocks (type 6)
    out: list[tuple[float, str, int, bytes]] = []   # (ts, dir, seq, payload)
    # First block = SHB; after that IDBs and EPBs
    link_type = 0
    i = 0
    while i < len(data):
        if i + 8 > len(data):
            break
        btype, blen = struct.unpack("<II", data[i:i + 8])
        body = data[i + 8: i + blen - 4]
        if btype == 0x00000001:   # IDB
            link_type = struct.unpack("<H", body[0:2])[0]
        elif btype == 0x00000006:  # EPB
            iface, ts_hi, ts_lo, cap_len, orig_len = struct.unpack("<IIIII", body[:20])
            ts = ((ts_hi << 32) | ts_lo) / 1_000_000.0
            packet = body[20: 20 + cap_len]
            _parse_packet(ts, packet, link_type, server_port, out)
        i += blen
    out.sort(key=lambda x: (x[0], x[2]))

    # Collapse adjacent chunks of same direction into one chunk per direction change
    chunks: list[tuple[str, bytes]] = []
    for _, direction, _, payload in out:
        if not payload:
            continue
        if chunks and chunks[-1][0] == direction:
            chunks[-1] = (direction, chunks[-1][1] + payload)
        else:
            chunks.append((direction, payload))
    return chunks


def _parse_packet(ts: float, pkt: bytes, link_type: int, server_port: int,
                  out: list[tuple[float, str, int, bytes]]) -> None:
    # Null link-type (0): 4-byte protocol family, then IP
    if link_type == 0:
        if len(pkt) < 4:
            return
        pf = struct.unpack("<I", pkt[:4])[0]
        if pf not in (2, 24, 28, 30):   # AF_INET variants
            return
        ip_offset = 4
    elif link_type == 1:   # Ethernet
        if len(pkt) < 14 or pkt[12:14] != b"\x08\x00":
            return
        ip_offset = 14
    else:
        return
    ipv = pkt[ip_offset] >> 4
    if ipv != 4:
        return
    ihl = (pkt[ip_offset] & 0x0F) * 4
    proto = pkt[ip_offset + 9]
    if proto != 6:
        return
    tcp = pkt[ip_offset + ihl:]
    if len(tcp) < 20:
        return
    sport, dport = struct.unpack("!HH", tcp[:4])
    seq = struct.unpack("!I", tcp[4:8])[0]
    data_off = (tcp[12] >> 4) * 4
    payload = tcp[data_off:]
    if sport == server_port:
        direction = "s2c"
    elif dport == server_port:
        direction = "c2s"
    else:
        return
    out.append((ts, direction, seq, payload))
