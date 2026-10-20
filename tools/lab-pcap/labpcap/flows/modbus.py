"""F7 - OSS01 (legitimate Modbus master) reads the Wago PLC every 1 s.
    Planted - UNKNOWN_GW polls every 10 s and makes a couple of setpoint writes.

Both use pymodbus client against a pymodbus server, 127.0.0.1 only.
"""
from __future__ import annotations

import threading
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext as ModbusSlaveContext
from pymodbus.server import StartTcpServer

from ..recorder import TcpRecorder, LOOPBACK
from ..tcp import TcpConv
from . import Ctx


def _start_wago(port: int):
    # Holding registers: a small block representing boiler pressure (0x0000), turbine speed
    # (0x0001), generator MW (0x0002), fuel feed rate (0x0003), setpoint (0x0010).
    hr = ModbusSequentialDataBlock(1, [1250, 3600, 18, 95, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 500] + [0] * 15)
    ir = ModbusSequentialDataBlock(1, [1250, 3600, 18, 95] + [0] * 28)
    slave = ModbusSlaveContext(hr=hr, ir=ir)
    ctx = ModbusServerContext(devices={1: slave}, single=False)
    t = threading.Thread(target=StartTcpServer, kwargs={"context": ctx, "address": (LOOPBACK, port)}, daemon=True)
    t.start()
    time.sleep(0.3)
    return ctx


def _record_cyclic_reads(port: int):
    rec = TcpRecorder(target_port=port)
    try:
        c = ModbusTcpClient(LOOPBACK, port=rec.listen_port, timeout=2)
        c.connect()
        # FC3: read holding registers 0..7
        c.read_holding_registers(address=0, count=8, device_id=1)
        time.sleep(0.02)
        c.close()
    finally:
        chunks = rec.take(settle=0.1, timeout=5.0)
        rec.close()
    return chunks


def _record_write(port: int, address: int, value: int):
    rec = TcpRecorder(target_port=port)
    try:
        c = ModbusTcpClient(LOOPBACK, port=rec.listen_port, timeout=2)
        c.connect()
        c.write_register(address=address, value=value, device_id=1)
        time.sleep(0.02)
        c.close()
    finally:
        chunks = rec.take(settle=0.1, timeout=5.0)
        rec.close()
    return chunks


def generate(ctx: Ctx) -> None:
    spec = ctx.spec
    mo = spec.flows["modbus_os"]
    pl = spec.flows["planted"]

    wago_port = 15020
    _start_wago(wago_port)

    read_chunks = _record_cyclic_reads(wago_port)
    write_chunks_1 = _record_write(wago_port, address=16, value=520)
    write_chunks_2 = _record_write(wago_port, address=16, value=540)
    read_chunks_alt = _record_cyclic_reads(wago_port)

    # Split a recorded read trace into (connect-handshake-already-done-in-TcpConv),
    # one request/reply pair. For Modbus/TCP a connect carries no app-layer setup, so each
    # request is self-contained; just emit the request and the reply.
    def _req_reply(chunks):
        req = next((d for d in chunks if d[0] == "c2s"), None)
        rep = next((d for d in chunks if d[0] == "s2c"), None)
        if req is None or rep is None:
            raise RuntimeError("short modbus trace")
        return [req, rep]

    legit_pair = _req_reply(read_chunks)
    planted_pair = _req_reply(read_chunks_alt)
    w1_pair = _req_reply(write_chunks_1)
    w2_pair = _req_reply(write_chunks_2)

    # ---------- F7: OSS01 holds a Modbus/TCP connection, polls every 1 s ----------
    client = spec.host(mo["client"])
    server = spec.host(mo["server"])
    seen_on = mo["seen_on"]
    conv = TcpConv(spec=spec, tl=ctx.tl, client=client, server=server, dport=502,
                   seen_on=seen_on, rng=ctx.rng)
    latency = {"c2s": (0.0002, 0.0006), "s2c": (0.0003, 0.0009)}
    t = conv.handshake(1.8, rtt=0.0010)
    period = mo["period_s"]
    base = t + 0.3
    i = 0
    while True:
        at = base + i * period + ctx.rng.uniform(-0.02, 0.04)
        if at >= ctx.duration - 2.0:
            break
        r = ctx.rng.random()
        if r < 0.008:   # occasional skipped poll
            i += 1
            continue
        conv.exchange(at, legit_pair, latency)
        if r < 0.02:    # occasional burst read after a slow one
            conv.exchange(at + 0.11 + ctx.rng.uniform(0, 0.04), legit_pair, latency)
        i += 1
    conv.close(ctx.duration - 1.8, who="c")
    conv.finish(ctx.duration)

    # ---------- planted: gateway polls every 10 s + 2 writes + outbound SYNs ----------
    pclient = spec.host(pl["client"])
    pconv = TcpConv(spec=spec, tl=ctx.tl, client=pclient, server=server, dport=502,
                    seen_on=seen_on, rng=ctx.rng)
    t = pconv.handshake(5.0, rtt=0.0008)
    pperiod = pl["period_s"]
    base = t + 0.5
    poll_times = [base + i * pperiod for i in range(int((ctx.duration - base - 2.0) / pperiod))]
    for at in poll_times:
        pconv.exchange(at + ctx.rng.uniform(-0.05, 0.05), planted_pair, latency)
    # two writes, interleaved on the same connection
    pconv.exchange(pl["writes_at_s"][0], w1_pair, latency)
    pconv.exchange(pl["writes_at_s"][1], w2_pair, latency)
    pconv.close(ctx.duration - 1.4, who="c")
    pconv.finish(ctx.duration)

    # Outbound SYNs to an internet host: emit as unanswered SYNs through FW-South MAC path.
    # The frame is seen on the Wago segment; src MAC is the gateway, dst MAC is OT-FW.wago
    # (its default gateway).
    from .. import frames as F
    from ..spec import Host
    internet = spec.host(pl["outbound_to"])
    gw_mac = spec.router_mac("OT-FW", "wago")
    out_period = pl["outbound_every_s"]
    for i in range(int(ctx.duration / out_period)):
        at = 30.0 + i * out_period + ctx.rng.uniform(-2.0, 2.0)
        if at >= ctx.duration - 5.0:
            break
        sport = ctx.rng.randint(49152, 65535)
        # SYN only (no reply), one each time
        import struct
        seq = ctx.rng.getrandbits(32)
        opts = struct.pack("!BBH", 2, 4, 1460)  # MSS
        tcp_hdr = struct.pack("!HHIIBBHHH", sport, 443, seq, 0, (6 << 4), 0x02, 29200, 0, 0) + opts
        csum = F.checksum(F.pseudo(pclient.ip, internet.ip, 6, len(tcp_hdr)) + tcp_hdr)
        tcp_hdr = tcp_hdr[:16] + struct.pack("!H", csum) + tcp_hdr[18:]
        ip = F.ipv4(pclient.ip, internet.ip, 6, tcp_hdr, ttl=pclient.profile["ttl"], ident=pclient.next_ip_id())
        ctx.tl.add(at, F.eth(pclient.mac, gw_mac, 0x0800, ip))
