"""Rebuild a TCP conversation (handshake, data, ACKs, close) around recorded payload bytes.

Per-OS behaviour comes from the spec profile: TTL, SYN window/options, scaled window,
SACK/timestamps (only when both ends offer them) and the delayed-ACK timer.
"""
from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field

from . import frames as F
from .spec import Host, Spec
from .timeline import Timeline

FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10


@dataclass
class _Side:
    host: Host
    port: int
    seq: int
    ts_base: int
    unacked_segs: int = 0
    ack_due: float | None = None
    last_tsval_rx: int = 0


@dataclass
class TcpConv:
    spec: Spec
    tl: Timeline
    client: Host
    server: Host
    dport: int
    seen_on: str
    rng: random.Random
    sport: int | None = None
    ws: bool = False
    sack: bool = False
    ts: bool = False
    sides: dict[str, _Side] = field(default_factory=dict)
    last_t: float = 0.0

    def __post_init__(self) -> None:
        lo, hi = self.client.profile["eph"]
        self.sport = self.sport or self.rng.randint(lo, hi)
        self.sides = {
            "c": _Side(self.client, self.sport, self.rng.getrandbits(32), self.rng.getrandbits(31)),
            "s": _Side(self.server, self.dport, self.rng.getrandbits(32), self.rng.getrandbits(31)),
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _peer(who: str) -> str:
        return "s" if who == "c" else "c"

    def _syn_opts(self, who: str, offered: dict[str, bool] | None, t: float) -> bytes:
        p = self.sides[who].host.profile
        want_ws = p["wscale"] > 0 and (offered is None or offered["ws"])
        want_sack = p["sack"] and (offered is None or offered["sack"])
        want_ts = p["ts"] and (offered is None or offered["ts"])
        mss = struct.pack("!BBH", 2, 4, p["mss"])
        ws = struct.pack("!BBB", 3, 3, p["wscale"]) if want_ws else b""
        sp = b"\x04\x02" if want_sack else b""
        tsopt = b""
        if want_ts:
            tsopt = struct.pack("!BBII", 8, 10, self._tsval(who, t), self.sides[who].last_tsval_rx)
        if self.sides[who].host.profile_name == "linux":   # MSS, SACK_PERM, TS, NOP, WS
            opts = mss + sp + tsopt + (b"\x01" + ws if ws else b"")
        else:                                                # Windows / embedded: MSS, NOP, WS, NOP, NOP, SACK_PERM
            opts = mss + (b"\x01" + ws if ws else b"") + (b"\x01\x01" + sp if sp else b"")
        opts += b"\x00" * ((4 - len(opts) % 4) % 4)
        return opts

    def _tsval(self, who: str, t: float) -> int:
        return (self.sides[who].ts_base + int(t * 1000)) & 0xFFFFFFFF

    def _window(self, who: str, syn: bool) -> int:
        p = self.sides[who].host.profile
        if syn or not self.ws:
            return min(p["syn_win"], 65535)
        return p["win"]

    def _emit(self, t: float, who: str, flags: int, payload: bytes = b"", opts: bytes | None = None) -> None:
        me, peer = self.sides[who], self.sides[self._peer(who)]
        src, dst = me.host, peer.host
        smac, dmac, dec = self.spec.view(src, dst, self.seen_on)
        if opts is None:
            opts = b""
            if self.ts and not flags & SYN:
                opts = b"\x01\x01" + struct.pack("!BBII", 8, 10, self._tsval(who, t), me.last_tsval_rx)
        ackno = peer.seq if flags & ACK else 0
        off = (20 + len(opts)) // 4
        hdr = struct.pack("!HHIIBBHHH", me.port, peer.port, me.seq, ackno, off << 4, flags,
                          self._window(who, bool(flags & SYN)), 0, 0) + opts
        csum = F.checksum(F.pseudo(src.ip, dst.ip, 6, len(hdr) + len(payload)) + hdr + payload)
        hdr = hdr[:16] + struct.pack("!H", csum) + hdr[18:]
        pkt = F.ipv4(src.ip, dst.ip, 6, hdr + payload, ttl=src.profile["ttl"] - dec, ident=src.next_ip_id())
        self.tl.add(t, F.eth(smac, dmac, 0x0800, pkt))
        peer.last_tsval_rx = self._tsval(who, t)
        me.seq = (me.seq + len(payload) + (1 if flags & (SYN | FIN) else 0)) & 0xFFFFFFFF
        self.last_t = max(self.last_t, t)

    def _flush_ack(self, who: str, before: float) -> None:
        """Send `who`'s pending delayed ACK if its timer fires before `before`."""
        side = self.sides[who]
        if side.ack_due is not None and side.ack_due <= before:
            self._emit(side.ack_due, who, ACK)
            side.ack_due, side.unacked_segs = None, 0

    # ------------------------------------------------------------------ public API
    def handshake(self, t: float, rtt: float = 0.0006) -> float:
        offered = {"ws": self.client.profile["wscale"] > 0, "sack": self.client.profile["sack"],
                   "ts": self.client.profile["ts"]}
        self._emit(t, "c", SYN, opts=self._syn_opts("c", None, t))
        sp = self.server.profile
        self.ws = offered["ws"] and sp["wscale"] > 0
        self.sack = offered["sack"] and sp["sack"]
        self.ts = offered["ts"] and sp["ts"]
        self._emit(t + rtt * 0.5, "s", SYN | ACK, opts=self._syn_opts("s", offered, t + rtt * 0.5))
        self._emit(t + rtt, "c", ACK)
        return t + rtt

    def send(self, t: float, who: str, data: bytes) -> float:
        """`who` sends `data` at t (split at MSS). Returns time of the last segment."""
        peer = self._peer(who)
        self._flush_ack(who, t)
        self._flush_ack(peer, t)
        mss = min(self.client.profile["mss"], self.server.profile["mss"])
        chunks = [data[i:i + mss] for i in range(0, len(data), mss)] or [b""]
        for i, part in enumerate(chunks):
            flags = ACK | (PSH if i == len(chunks) - 1 else 0)
            self._emit(t, who, flags, part)
            # receiver: piggyback on its next send, or ACK every 2nd full segment / after delack
            ps = self.sides[peer]
            ps.unacked_segs += 1
            if ps.unacked_segs >= 2:
                self._emit(t + 0.00004, peer, ACK)
                ps.unacked_segs, ps.ack_due = 0, None
            elif ps.ack_due is None:
                ps.ack_due = t + ps.host.profile["delack_ms"] / 1000.0
            self.sides[who].ack_due, self.sides[who].unacked_segs = None, 0   # our data acked theirs
            t += 0.00002 + len(part) * 8 / 1e9
        return t

    def exchange(self, t: float, chunks: list[tuple[str, bytes]], latency: dict[str, tuple[float, float]]) -> float:
        """Replay recorded chunks starting at t. latency[dir] = (min,max) seconds before a reply in `dir`."""
        prev = None
        for direction, data in chunks:
            who = "c" if direction == "c2s" else "s"
            if prev is not None:
                if direction != prev:
                    t += self.rng.uniform(*latency[direction])
                else:
                    t += self.rng.uniform(0.00005, 0.0003)
            t = self.send(t, who, data)
            prev = direction
        return t

    def close(self, t: float, who: str = "c") -> float:
        peer = self._peer(who)
        self._flush_ack(who, t)
        self._flush_ack(peer, t)
        self._emit(t, who, FIN | ACK)
        t2 = t + self.rng.uniform(0.0003, 0.002)
        self._emit(t2, peer, FIN | ACK)
        self._emit(t2 + 0.0004, who, ACK)
        for s in self.sides.values():
            s.ack_due = None
        return t2 + 0.0004

    def finish(self, horizon: float) -> None:
        for who in ("c", "s"):
            self._flush_ack(who, horizon)
