"""Reachability probing — cheap TCP connects that feed the dashboard chips and inform
transport selection. No auth, no payload; just "is this port open from MC01 right now".
"""

from __future__ import annotations

import asyncio

from app.models.api import Reachability
from app.models.inventory import OS, Target

# port -> which reachability field it sets
PORTS = {
    5985: "winrm",
    22: "ssh",
    445: "smb",
    3389: "rdp",
    443: "https",
}


async def _port_open(host: str, port: int, timeout: float) -> bool:
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _ports_for(target: Target) -> list[int]:
    """Only probe ports that make sense for the target, to keep the sweep fast."""
    if not target.address:
        return []
    if target.os in (OS.LINUX, OS.NETWORK):
        return [22, 443]
    if target.os == OS.APPLIANCE:
        return [443]
    # windows host or guest
    return [5985, 445, 3389, 443]


async def probe_target(target: Target, timeout: float = 1.5) -> Reachability:
    r = Reachability()
    ports = _ports_for(target)
    results = await asyncio.gather(
        *(_port_open(target.address, p, timeout) for p in ports), return_exceptions=True
    )
    for port, ok in zip(ports, results):
        field = PORTS[port]
        setattr(r, field, bool(ok) if not isinstance(ok, Exception) else False)
    return r


async def probe_all(targets: list[Target], timeout: float = 1.5) -> dict[str, Reachability]:
    out = await asyncio.gather(*(probe_target(t, timeout) for t in targets))
    return {t.name: r for t, r in zip(targets, out)}
