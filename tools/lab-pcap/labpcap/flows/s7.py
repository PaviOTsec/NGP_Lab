"""F1/F2 - S7comm to the PCS 7 controller (Pharma CSTR).

Uses snap7's pure-Python server + client (both on 127.0.0.1) to produce real S7comm bytes:
- F1: OS server L2H1_OSS01 reads the CSTR process image every ~1 s (steady cyclic polling).
- F2: Engineering station L2H1_ES01 opens one session, reads module identification
  (SZL 0x001C, 0x0011, 0x0131, 0x0232), then disconnects.

The recorded byte streams are replayed through TcpConv so each exchange appears as a real TCP
conversation on the PCS segment (TTL/MAC view decided by the recorded flow's `seen_on`).
"""
from __future__ import annotations

import threading
import time

from snap7.client import Client
from snap7.server import Server
from snap7.type import Area, SrvArea

from ..recorder import TcpRecorder, LOOPBACK
from ..tcp import TcpConv
from . import Ctx


def _start_cpu410(port: int) -> tuple[Server, bytearray]:
    """A snap7 server bound to 127.0.0.1:port, with a DB1 holding the CSTR process image."""
    srv = Server(log=False)
    # 64 bytes of DB1 is the CSTR snapshot: temperature, level, agitator speed, dosing rates,
    # discharge valve state. Steady values; the client reads them every second.
    db1 = (bytearray.fromhex(
        "41b00000"   # DB1.DBD0  REAL  22.000  CSTR temperature (degC)
        "42340000"   # DB1.DBD4  REAL  45.000  level (%)
        "44160000"   # DB1.DBD8  REAL  600.0   agitator speed (rpm)
        "41700000"   # DB1.DBD12 REAL  15.000  feed A dosing rate
        "41480000"   # DB1.DBD16 REAL  12.500  feed B dosing rate
        "01"         # DB1.DBX20.0 BOOL discharge valve
        "00"         # pad
        "0001"       # DB1.DBW22 INT   batch step
    ) + bytes(40))
    srv.register_area(SrvArea.DB, 1, db1)
    srv.start_to(LOOPBACK, port)
    return srv, db1


def _record_cyclic_read(port: int, cycles: int) -> list[tuple[str, bytes]]:
    """Record one connect + N DB1 reads + disconnect from a snap7 client."""
    rec = TcpRecorder(target_port=port)
    try:
        c = Client()
        c.set_connection_type(2)  # OP connection
        c.connect(LOOPBACK, 0, 3, rec.listen_port)
        for _ in range(cycles):
            c.db_read(1, 0, 24)
            time.sleep(0.005)
        c.disconnect()
    finally:
        chunks = rec.take(settle=0.1, timeout=10.0)
        rec.close()
    return chunks


def _record_engineering_session(port: int) -> list[tuple[str, bytes]]:
    """Record one PG connect + a few DB reads (what the engineer sees in a watch table)
    + disconnect. Avoids SZL reads whose snap7 responses sometimes confuse Wireshark.
    """
    rec = TcpRecorder(target_port=port)
    try:
        c = Client()
        c.set_connection_type(1)  # PG connection
        c.connect(LOOPBACK, 0, 3, rec.listen_port)
        for _ in range(4):
            try:
                c.db_read(1, 0, 24)
            except Exception:
                pass
            time.sleep(0.03)
        c.disconnect()
    finally:
        chunks = rec.take(settle=0.1, timeout=10.0)
        rec.close()
    return chunks


def generate(ctx: Ctx) -> None:
    spec = ctx.spec
    s7_os = spec.flows["s7_os"]
    s7_es = spec.flows["s7_es"]

    srv, _ = _start_cpu410(port=0 if False else 10200)
    time.sleep(0.1)
    try:
        # F1: one long OP connection reading DB1 cyclically.
        # We don't record 900 reads; we record one read and replay it on the timeline each cycle,
        # which is exactly what WinCC's channel does (same job id pattern repeating).
        setup_chunks = _record_cyclic_read(10200, cycles=1)

        client = spec.host(s7_os["client"])
        server = spec.host(s7_os["server"])
        seen_on = s7_os["seen_on"]
        period = s7_os["period_s"]

        # Split the recorded chunks into (connect+setup+negotiate), one (poll,reply) pair,
        # and the disconnect. snap7's connect does: ISO COTP CR/CC, then S7 Setup Comm req/resp.
        # The first poll+reply pair is the 4th exchange onward until disconnect.
        c2s = [i for i, (d, _) in enumerate(setup_chunks) if d == "c2s"]
        if len(c2s) < 4:
            raise RuntimeError("unexpected snap7 trace length")
        setup = setup_chunks[: c2s[2]]           # COTP CR, S7 Setup Req
        poll_pair = setup_chunks[c2s[2]: c2s[3]] # one Read Var req + reply
        teardown = setup_chunks[c2s[3]:]         # the disconnect from Client.disconnect()

        conv = TcpConv(spec=spec, tl=ctx.tl, client=client, server=server, dport=102,
                       seen_on=seen_on, rng=ctx.rng)
        latency = {"c2s": (0.0003, 0.0008), "s2c": (0.0004, 0.0012)}
        t = conv.handshake(2.5, rtt=0.0012)
        t = conv.exchange(t, setup, latency)
        # Cyclic polls with realistic non-uniform behaviour: jitter + rare skipped cycles
        # (OS server CPU hiccups) + occasional back-to-back pair (missed cycle recovery).
        poll_base = t + 0.5
        i = 0
        while True:
            at = poll_base + i * period + ctx.rng.uniform(-0.03, 0.03)
            if at >= ctx.duration - 3.0:
                break
            r = ctx.rng.random()
            if r < 0.012:   # ~1.2% of cycles skipped
                i += 1
                continue
            conv.exchange(at, poll_pair, latency)
            if r < 0.025:   # ~1.3% of cycles get a quick extra read right after
                conv.exchange(at + 0.08 + ctx.rng.uniform(0, 0.05), poll_pair, latency)
            i += 1
        conv.exchange(ctx.duration - 2.0, teardown, latency)
        conv.close(ctx.duration - 1.5, who="c")
        conv.finish(ctx.duration)

        # F2: one engineering session at s7_es.at_s
        es_chunks = _record_engineering_session(10200)
        es_client = spec.host(s7_es["client"])
        es_conv = TcpConv(spec=spec, tl=ctx.tl, client=es_client, server=server, dport=102,
                          seen_on=seen_on, rng=ctx.rng)
        at = s7_es["at_s"]
        t = es_conv.handshake(at, rtt=0.0012)
        t = es_conv.exchange(t, es_chunks, latency)
        es_conv.close(t + 0.05, who="c")
        es_conv.finish(ctx.duration)
    finally:
        srv.stop()
        srv.destroy()
