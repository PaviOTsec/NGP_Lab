"""F4/F5/F6 - IEC 61850 for the Transmission/Distribution cell.

F4: RTU (SICAM A8000 role) is the station client; reads IED model, enables reports, receives
    periodic reports from IED1 and IED2.
F6: OSS01 is a second MMS client against the RTU, treating it as substation gateway.
F5: Both IEDs publish GOOSE heartbeats ~1 s; IED2 bursts on one event (breaker open).

GOOSE frames are raw Ethernet (0x88B8); we build them by hand to a format that dissects
cleanly as libiec61850's own publisher would produce on the wire.
"""
from __future__ import annotations

import struct
import threading
import time

import pyiec61850.pyiec61850 as L

from pathlib import Path

from ..loopcap import LoopbackCapture, extract_tcp
from ..recorder import TcpRecorder, LOOPBACK
from ..tcp import TcpConv
from . import Ctx

_SCRATCH = Path("C:/Users/Administrator/AppData/Local/Temp/claude/labpcap-iec")
_SCRATCH.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------- MMS server + client
def _build_breaker_model(ied_name: str):
    m = L.IedModel_create(ied_name)
    ld = L.LogicalDevice_create("CTRL", m)
    lln0 = L.LogicalNode_create("LLN0", ld)
    xcbr = L.LogicalNode_create("XCBR1", ld)
    mmxu = L.LogicalNode_create("MMXU1", ld)
    L.CDC_ENS_create("Mod", L.toModelNode(lln0), 0)
    L.CDC_ENS_create("Beh", L.toModelNode(lln0), 0)
    L.CDC_DPS_create("Pos", L.toModelNode(xcbr), 0)
    L.CDC_SPS_create("Loc", L.toModelNode(xcbr), 0)
    L.CDC_MV_create("TotW", L.toModelNode(mmxu), 0, False)
    L.CDC_MV_create("Hz", L.toModelNode(mmxu), 0, False)
    ds = L.DataSet_create("dsStatus", lln0)
    L.DataSetEntry_create(ds, "CTRL/XCBR1$ST$Pos", -1, None)
    L.DataSetEntry_create(ds, "CTRL/MMXU1$MX$TotW", -1, None)
    L.DataSetEntry_create(ds, "CTRL/MMXU1$MX$Hz", -1, None)
    L.ReportControlBlock_create(
        "urcbStatus", lln0,
        f"{ied_name}CTRL/LLN0$RP$urcbStatus", False, "dsStatus", 1,
        L.TRG_OPT_DATA_CHANGED | L.TRG_OPT_INTEGRITY | L.TRG_OPT_GI,
        L.RPT_OPT_SEQ_NUM | L.RPT_OPT_TIME_STAMP | L.RPT_OPT_REASON_FOR_INCLUSION | L.RPT_OPT_DATA_SET,
        50, 10000,
    )
    return m


def _start_ied(ied_name: str, port: int):
    model = _build_breaker_model(ied_name)
    srv = L.IedServer_create(model)
    L.IedServer_setLocalIpAddress(srv, LOOPBACK)
    L.IedServer_start(srv, port)
    return srv, model


def _record_mms_session(port: int, kind: str, ied_prefix: str) -> list[tuple[str, bytes]]:
    """Browse the server and read a handful of attributes to produce real MMS Read requests.

    Uses Npcap loopback capture (not a TCP proxy) because libiec61850's connect sequence is
    sensitive to proxy latency and will time out even on localhost.
    """
    pcap_path = _SCRATCH / f"mms_{port}_{kind}.pcapng"
    with LoopbackCapture(pcap_path):
        con = L.IedConnection_create()
        err = L.IedConnection_connect(con, LOOPBACK, port)
        if err[1] != 0:
            L.IedConnection_destroy(con)
            raise RuntimeError(f"IedConnection_connect returned {err[1]}")
        try:
            L.IedConnection_getLogicalDeviceList(con)
            try:
                L.IedConnection_getLogicalNodeDirectory(con, f"{ied_prefix}CTRL/LLN0", L.ACSI_CLASS_DATA_SET)
            except Exception:
                pass
            for ref, fc in [
                (f"{ied_prefix}CTRL/XCBR1.Pos.stVal", L.IEC61850_FC_ST),
                (f"{ied_prefix}CTRL/MMXU1.TotW.mag.f", L.IEC61850_FC_MX),
                (f"{ied_prefix}CTRL/MMXU1.Hz.mag.f", L.IEC61850_FC_MX),
                (f"{ied_prefix}CTRL/LLN0.Mod.stVal", L.IEC61850_FC_ST),
            ]:
                try:
                    L.IedConnection_readObject(con, ref, fc)
                except Exception:
                    pass
                time.sleep(0.03)
            if kind == "full":
                for ref, fc in [
                    (f"{ied_prefix}CTRL/XCBR1.Loc.stVal", L.IEC61850_FC_ST),
                    (f"{ied_prefix}CTRL/MMXU1.TotW.q", L.IEC61850_FC_MX),
                    (f"{ied_prefix}CTRL/MMXU1.Hz.q", L.IEC61850_FC_MX),
                ]:
                    try:
                        L.IedConnection_readObject(con, ref, fc)
                    except Exception:
                        pass
                    time.sleep(0.04)
        finally:
            L.IedConnection_close(con)
            L.IedConnection_destroy(con)
        time.sleep(0.4)
    return extract_tcp(pcap_path, server_port=port)


# ---------------------------------------------------------------------- GOOSE builder
def _goose_frame(src_mac: str, dst_mac: str, go_cb_ref: str, dat_set: str, go_id: str,
                 st_num: int, sq_num: int, t_ms: int, pos_value: int) -> bytes:
    """Minimal GOOSE PDU with a DOUBLE-POINT (bitstring 2) + TotW float + quality + timestamp."""
    from ..frames import mac_bytes

    def _tag(tag: int, data: bytes) -> bytes:
        if len(data) < 128:
            return bytes([tag, len(data)]) + data
        if len(data) < 256:
            return bytes([tag, 0x81, len(data)]) + data
        return bytes([tag, 0x82, len(data) >> 8, len(data) & 0xFF]) + data

    def _int(tag: int, v: int) -> bytes:
        b = v.to_bytes(max(1, (v.bit_length() + 7) // 8), "big") if v >= 0 else b"\xFF"
        return _tag(tag, b)

    def _bool(tag: int, v: bool) -> bytes:
        return _tag(tag, b"\xff" if v else b"\x00")

    def _str(tag: int, s: str) -> bytes:
        return _tag(tag, s.encode("ascii"))

    def _utctime(tag: int, ms: int) -> bytes:
        secs = ms // 1000
        frac = int(((ms % 1000) / 1000.0) * (1 << 24))
        return _tag(tag, struct.pack(">I", secs) + struct.pack(">I", frac << 0)[1:4] + bytes([0x0A]))

    def _data_bitstring2(v: int) -> bytes:
        # TAG 0x84 bitstring, 2 bits = double point: 1 = off, 2 = on
        bits = {0: 0x00, 1: 0x80, 2: 0x40, 3: 0xC0}[v & 0x03]
        return _tag(0x84, bytes([6, bits]))  # 6 unused bits in last octet

    def _data_float(v: float) -> bytes:
        return _tag(0x87, b"\x08" + struct.pack(">f", v))

    def _data_quality() -> bytes:
        return _tag(0x84, bytes([3, 0x00]))  # 13-bit quality, 3 unused bits, all zero

    # all data elements wrapped in SEQUENCE OF Data (tag 0xAB "allData")
    data = _data_bitstring2(pos_value) + _data_float(600.0) + _data_float(50.0)
    all_data = _tag(0xAB, data)

    pdu_body = (
        _str(0x80, go_cb_ref)
        + _int(0x81, 2000)       # timeAllowedtoLive (ms)
        + _str(0x82, dat_set)
        + _str(0x83, go_id)
        + _utctime(0x84, t_ms)
        + _int(0x85, st_num)
        + _int(0x86, sq_num)
        + _bool(0x87, False)     # test
        + _int(0x88, 1)          # confRev
        + _bool(0x89, False)     # ndsCom
        + _int(0x8A, 3)          # numDatSetEntries
        + all_data
    )
    goose_pdu = _tag(0x61, pdu_body)

    # Ethernet II header without 802.1Q tag (per D14 / most lab deployments), with APPID + length.
    appid = 0x0003
    reserved1 = 0
    reserved2 = 0
    length = 8 + len(goose_pdu)
    goose = struct.pack(">HHHH", appid, length, reserved1, reserved2) + goose_pdu

    dst = mac_bytes(dst_mac)
    src = mac_bytes(src_mac)
    frame = dst + src + struct.pack(">H", 0x88B8) + goose
    if len(frame) < 60:
        frame += b"\x00" * (60 - len(frame))
    return frame


# ---------------------------------------------------------------------- flow entry point
def generate(ctx: Ctx) -> None:
    spec = ctx.spec
    f_rtu_ied = spec.flows["mms_rtu_ied"]
    f_os_rtu = spec.flows["mms_os_rtu"]
    f_goose = spec.flows["goose"]

    # ------- IED1 as MMS server (port 10210), IED2 as MMS server (10211) -------
    ied1_srv, m1 = _start_ied("SIP5BRK1", 10210)
    ied2_srv, m2 = _start_ied("SIP5BRK2", 10211)
    time.sleep(0.2)
    try:
        rtu_to_ied1 = _record_mms_session(10210, kind="full", ied_prefix="SIP5BRK1")
        rtu_to_ied2 = _record_mms_session(10211, kind="full", ied_prefix="SIP5BRK2")
    finally:
        L.IedServer_stop(ied1_srv)
        L.IedServer_destroy(ied1_srv)
        L.IedServer_stop(ied2_srv)
        L.IedServer_destroy(ied2_srv)

    # ------- RTU itself answers OSS01 (RTU acts as a gateway with its own MMS server) -------
    rtu_srv, m_rtu = _start_ied("A8000RTU", 10212)
    time.sleep(0.2)
    try:
        os_to_rtu = _record_mms_session(10212, kind="light", ied_prefix="A8000RTU")
    finally:
        L.IedServer_stop(rtu_srv)
        L.IedServer_destroy(rtu_srv)

    latency = {"c2s": (0.0003, 0.0010), "s2c": (0.0004, 0.0015)}

    # F4: RTU -> IED1
    rtu = spec.host(f_rtu_ied["client"])
    ied1 = spec.host(f_rtu_ied["servers"][0])
    ied2 = spec.host(f_rtu_ied["servers"][1])
    seen = f_rtu_ied["seen_on"]

    c1 = TcpConv(spec=spec, tl=ctx.tl, client=rtu, server=ied1, dport=102,
                 seen_on=seen, rng=ctx.rng)
    t = c1.handshake(3.2, rtt=0.0012)
    t = c1.exchange(t, rtu_to_ied1, latency)
    c1.close(ctx.duration - 2.0, who="c")
    c1.finish(ctx.duration)

    c2 = TcpConv(spec=spec, tl=ctx.tl, client=rtu, server=ied2, dport=102,
                 seen_on=seen, rng=ctx.rng)
    t = c2.handshake(3.6, rtt=0.0012)
    t = c2.exchange(t, rtu_to_ied2, latency)
    c2.close(ctx.duration - 1.9, who="c")
    c2.finish(ctx.duration)

    # F6: OSS01 -> RTU
    oss = spec.host(f_os_rtu["client"])
    c3 = TcpConv(spec=spec, tl=ctx.tl, client=oss, server=rtu, dport=102,
                 seen_on=f_os_rtu["seen_on"], rng=ctx.rng)
    t = c3.handshake(4.1, rtt=0.0012)
    t = c3.exchange(t, os_to_rtu, latency)
    c3.close(t + 0.2, who="c")
    c3.finish(ctx.duration)

    # F5: GOOSE heartbeats from IED1 and IED2 ---------------------------------
    heartbeat = f_goose["heartbeat_s"]
    event_t = f_goose["event"]["at_s"]
    event_ied = f_goose["event"]["ied"]
    goose_seen = f_goose["seen_on"]

    for ied_name, go_mac in (("IED1", "01:0c:cd:01:00:01"), ("IED2", "01:0c:cd:01:00:02")):
        ied_host = spec.host(ied_name)
        st_num = 1
        sq_num = 0
        pos = 2  # 'on' / closed
        t0 = 0.5 if ied_name == "IED1" else 0.9
        n = int((ctx.duration - t0) / heartbeat)
        for i in range(n):
            at = t0 + i * heartbeat + ctx.rng.uniform(-0.01, 0.01)
            start_epoch = spec.start_epoch
            t_ms = int((start_epoch + at) * 1000)
            # On event: IED2 toggles pos and st_num increments; emit a rapid burst
            if ied_name == event_ied and abs(at - event_t) < heartbeat / 2 and sq_num == 0 and st_num == 1:
                st_num = 2
                pos = 1  # open
                for k, dt in enumerate([0.0, 0.004, 0.008, 0.016, 0.032, 0.064, 0.128, 0.256, 0.512]):
                    frame = _goose_frame(
                        src_mac=ied_host.mac, dst_mac=go_mac,
                        go_cb_ref=f"{ied_name}CTRL/LLN0$GO$gcbStatus",
                        dat_set=f"{ied_name}CTRL/LLN0$dsStatus",
                        go_id=f"{ied_name}_Status",
                        st_num=st_num, sq_num=k,
                        t_ms=t_ms + int(dt * 1000),
                        pos_value=pos,
                    )
                    ctx.tl.add(at + dt, frame)
                sq_num = 10
                continue
            frame = _goose_frame(
                src_mac=ied_host.mac, dst_mac=go_mac,
                go_cb_ref=f"{ied_name}CTRL/LLN0$GO$gcbStatus",
                dat_set=f"{ied_name}CTRL/LLN0$dsStatus",
                go_id=f"{ied_name}_Status",
                st_num=st_num, sq_num=sq_num,
                t_ms=t_ms, pos_value=pos,
            )
            ctx.tl.add(at, frame)
            sq_num = min(sq_num + 1, 0xFFFF)
