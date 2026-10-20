"""Load the capture spec and answer 'what does this flow look like on segment X?'.

Topology: segments are nodes; each router connects the segments it has an interface on.
A frame seen on a SPAN of segment V carries:
  src MAC = the sender's MAC if it lives on V, else the MAC of the router that forwarded it onto V
  dst MAC = the receiver's MAC if it lives on V, else the MAC of the next-hop router on V
  TTL     = the sender's initial TTL minus the routers crossed before reaching V
"""
from __future__ import annotations

import ipaddress
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Host:
    name: str
    ip: str
    mac: str | None
    seg: str
    profile: dict[str, Any]
    profile_name: str
    raw: dict[str, Any]
    ip_id: int = 0

    def next_ip_id(self) -> int:
        self.ip_id = (self.ip_id + 1) & 0xFFFF
        return self.ip_id


@dataclass
class Spec:
    path: Path
    data: dict[str, Any]
    hosts: dict[str, Host] = field(default_factory=dict)
    # graph[seg] = list of (router_name, neighbour_seg)
    graph: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    @property
    def capture(self) -> dict[str, Any]:
        return self.data["capture"]

    @property
    def flows(self) -> dict[str, Any]:
        return self.data["flows"]

    @property
    def start_epoch(self) -> float:
        return datetime.fromisoformat(self.capture["start"]).timestamp()

    def host(self, name: str) -> Host:
        return self.hosts[name]

    def router_mac(self, router: str, seg: str) -> str:
        return self.data["routers"][router]["ifaces"][seg]["mac"]

    def router_ip(self, router: str, seg: str) -> str:
        return self.data["routers"][router]["ifaces"][seg]["ip"]

    def gateway_ip(self, seg: str) -> str:
        """The default gateway a host on `seg` ARPs for (first router listed with an iface there)."""
        prefer = {"l2": "OT-FW"}  # L2 hosts reach the cells via the OT-FW
        for rname, r in self.data["routers"].items():
            if seg in r["ifaces"] and prefer.get(seg, rname) == rname:
                return r["ifaces"][seg]["ip"]
        raise KeyError(seg)

    # ------------------------------------------------------------------ routing
    def _path(self, a: str, b: str) -> list[tuple[str | None, str]]:
        """Segments from a to b as [(router_used_to_enter, seg), ...]; first entry router=None."""
        prev: dict[str, tuple[str | None, str | None]] = {a: (None, None)}
        q = deque([a])
        while q:
            s = q.popleft()
            if s == b:
                break
            for router, nxt in self.graph.get(s, []):
                if nxt not in prev:
                    prev[nxt] = (router, s)
                    q.append(nxt)
        if b not in prev:
            raise ValueError(f"no route {a} -> {b}")
        out: list[tuple[str | None, str]] = []
        cur: str | None = b
        while cur is not None:
            router, before = prev[cur]
            out.append((router, cur))
            cur = before
        return list(reversed(out))

    def view(self, src: Host, dst: Host, seen_on: str) -> tuple[str, str, int]:
        """(src_mac, dst_mac, ttl_decrement) for a src->dst IP packet captured on `seen_on`."""
        path = self._path(src.seg, dst.seg)
        segs = [s for _, s in path]
        if seen_on not in segs:
            raise ValueError(f"{src.name}->{dst.name} never crosses {seen_on} (path {segs})")
        i = segs.index(seen_on)
        src_mac = src.mac if i == 0 else self.router_mac(path[i][0], seen_on)  # type: ignore[arg-type]
        dst_mac = dst.mac if i == len(path) - 1 else self.router_mac(path[i + 1][0], seen_on)  # type: ignore[arg-type]
        return src_mac, dst_mac, i  # one router crossed per hop before V


def load(path: str | Path) -> Spec:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    spec = Spec(path=p, data=data)
    for h in data["hosts"]:
        prof = dict(data["profiles"][h["profile"]])
        spec.hosts[h["name"]] = Host(name=h["name"], ip=h["ip"], mac=h.get("mac"), seg=h["seg"],
                                     profile=prof, profile_name=h["profile"], raw=h)
    for rname, r in data["routers"].items():
        segs = list(r["ifaces"])
        for s in segs:
            for t in segs:
                if s != t:
                    spec.graph.setdefault(s, []).append((rname, t))
    # sanity: every host IP sits in its segment's subnet
    for h in spec.hosts.values():
        net = ipaddress.ip_network(data["segments"][h.seg]["subnet"])
        if ipaddress.ip_address(h.ip) not in net:
            raise ValueError(f"{h.name} {h.ip} not in {h.seg} {net}")
        if ipaddress.ip_address(h.ip) in ipaddress.ip_network("192.168.2.0/24"):
            raise ValueError("SIS addresses must never appear in the capture (D20)")
    return spec
