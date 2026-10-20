"""F3 - PROFINET IO cyclic traffic (CPU 410 <-> ET 200SP) and ES01 DCP Identify.
Also LLDP announcements from the PCS devices.

Only non-TCP, repeating frames here. Formats match the Wireshark dissectors so no "malformed"
warnings appear. All PCS segment traffic (D18 vantage point).
"""
from __future__ import annotations

import struct

from .. import frames as F
from . import Ctx


# ---------------------------------------------------------------------- PROFINET RT
def _pnio_rt(src: str, dst: str, frame_id: int, cycle: int, data: bytes) -> bytes:
    """One PROFINET RT frame. frame_id in the DataExchange range (0x8000-0xBFFF for outputs,
    0xC000-0xFBFF for inputs; subset used by Siemens cells).

    APDU trailer (CycleCounter + DataStatus + TransferStatus) must be the last 4 bytes.
    """
    cycle_counter = cycle & 0xFFFF
    data_status = 0x35          # Primary, Valid, Run, no StationProblem (Wireshark 'OK')
    transfer_status = 0
    apdu_status = struct.pack(">HBB", cycle_counter, data_status, transfer_status)
    # PROFINET RT has no length field — Wireshark reads the APDU trailer as the last 4 bytes of
    # the Ethernet payload. The frame must therefore be >= 60 bytes (min Ethernet) with no
    # extra padding after the trailer. We pre-pad DATA so the eth() helper doesn't add any.
    needed_payload = 46                                 # 60-byte Ethernet frame minus 14-byte header
    data_pad = needed_payload - 2 - len(data) - 4       # frame_id(2) + data + trailer(4)
    if data_pad > 0:
        data = data + b"\x00" * data_pad
    body = struct.pack(">H", frame_id) + data + apdu_status
    return F.eth(src, dst, 0x8892, body)


def _dcp_identify_all() -> bytes:
    """DCP Identify.All multicast - what 'accessible devices' sends from an engineering station."""
    # ServiceID=5 (Identify), ServiceType=0 (Request)
    # XID (transaction) + ResponseDelay + DCPDataLength + one 'All selector' block
    xid = 0x12345678
    rsp_delay = 0x0000
    # Block: option 0xFF (All), suboption 0xFF, block length 0
    block = struct.pack(">BBH", 0xFF, 0xFF, 0)
    data_len = len(block)
    pnio_cm = struct.pack(">BBIHH", 5, 0, xid, rsp_delay, data_len) + block
    # FrameID for DCP Identify request = 0xFEFE
    return struct.pack(">H", 0xFEFE) + pnio_cm


def _lldpdu(chassis_mac: str, port_name: str, ttl: int = 20, sys_name: str = "") -> bytes:
    """Minimal valid LLDPDU: Chassis ID (subtype 4 = MAC), Port ID (subtype 7 = local), TTL, End."""
    def tlv(ttype: int, body: bytes) -> bytes:
        hdr = ((ttype & 0x7F) << 9) | (len(body) & 0x01FF)
        return struct.pack(">H", hdr) + body

    chassis_bytes = bytes(int(x, 16) for x in chassis_mac.split(":"))
    chassis = tlv(1, b"\x04" + chassis_bytes)                   # subtype 4 = MAC address
    port = tlv(2, b"\x07" + port_name.encode("ascii"))          # subtype 7 = locally assigned
    ttl_tlv = tlv(3, struct.pack(">H", ttl))
    pdu = chassis + port + ttl_tlv
    if sys_name:
        pdu += tlv(5, sys_name.encode("ascii"))
    pdu += tlv(0, b"")
    return pdu


# ---------------------------------------------------------------------- entry point
def generate(ctx: Ctx) -> None:
    spec = ctx.spec
    pn = spec.flows["pnio"]
    dcp = spec.flows["dcp_es"]

    cpu = spec.host(pn["controller"])
    et = spec.host(pn["device"])
    es = spec.host(dcp["client"])
    cycle_s = pn["cycle_ms"] / 1000.0

    # Controller output frame (IO AR 'outputs'): FrameID 0x8001; 12 bytes of outputs
    # Device input frame: FrameID 0xC001; 24 bytes of inputs
    n = int(ctx.duration / cycle_s)
    for i in range(n):
        t = i * cycle_s
        # outputs (CPU -> ET): includes setpoints to valves
        out = bytes([0, 0, 0, 0,  0x01, 0x00,  0, 0, 0, 0, 0, 0])
        ctx.tl.add(t, _pnio_rt(cpu.mac, et.mac, 0x8001, i, out))
        # inputs (ET -> CPU): slightly later in the cycle
        inp = (bytes([0x01, 0x00])
               + struct.pack(">f", 22.0 + 0.5 * ((i // 30) % 2))   # feed A level
               + struct.pack(">f", 44.5 + 0.2 * ((i // 50) % 3))   # tank level
               + bytes(14))
        ctx.tl.add(t + cycle_s * 0.4, _pnio_rt(et.mac, cpu.mac, 0xC001, i, inp))

    # LLDP every 5 s between the PCS switches and devices
    for h_name in pn.get("", []):
        pass
    for host_name in ("CPU410", "ET200SP", "SW-PCS"):
        h = spec.host(host_name)
        for i in range(int(ctx.duration / 5.0)):
            t = 2.0 + i * 5.0 + ctx.rng.uniform(-0.1, 0.1)
            pdu = _lldpdu(chassis_mac=h.mac, port_name="port-001", ttl=20, sys_name=h.raw.get("station", h.name))
            ctx.tl.add(t, F.eth(h.mac, "01:80:c2:00:00:0e", 0x88CC, pdu))

    # F2 companion: ES01 DCP Identify.All (xid 0x12345678), one burst at dcp.at_s
    dcp_frame_id = 0xFEFE
    at = dcp["at_s"]
    ctx.tl.add(at, F.eth(es.mac, "01:0e:cf:00:00:00", 0x8892, _dcp_identify_all()))
    # Responses from CPU410 and ET200SP ~2-5 ms later
    for h, resp_delay_ms in ((cpu, 3), (et, 7)):
        resp = _dcp_identify_response(h, 0x12345678)
        ctx.tl.add(at + resp_delay_ms / 1000.0, F.eth(h.mac, es.mac, 0x8892, resp))


def _dcp_identify_response(host, xid: int) -> bytes:
    """DCP Identify response, with Device Options + Device Properties + Name of Station + IP block."""
    station = host.raw.get("station", host.name.lower())
    ip_parts = [int(p) for p in host.ip.split(".")]

    def _block(opt: int, sub: int, body: bytes) -> bytes:
        total = len(body)
        pad = total % 2
        return struct.pack(">BBH", opt, sub, total) + body + (b"\x00" * pad)

    # Device Properties: Name of Station (opt 0x02, sub 0x02)
    name_block = _block(0x02, 0x02, struct.pack(">H", 0) + station.encode("ascii"))
    # Device ID (opt 0x02, sub 0x03): vendor id + device id (Siemens vendor 0x002A)
    devid_block = _block(0x02, 0x03, struct.pack(">H", 0) + struct.pack(">HH", 0x002A, 0x010B))
    # Device Role (opt 0x02, sub 0x04): IO Controller (0x02) or IO Device (0x01)
    role = 0x02 if host.name == "CPU410" else 0x01
    role_block = _block(0x02, 0x04, struct.pack(">HBB", 0, role, 0))
    # Device Options (opt 0x02, sub 0x05): advertise the common options
    opts_block = _block(0x02, 0x05, struct.pack(">H", 0) + bytes([0x02, 0x02, 0x02, 0x03, 0x02, 0x04, 0x01, 0x02]))
    # IP parameter (opt 0x01, sub 0x02): block info + IP + mask + gateway
    ip_block = _block(0x01, 0x02,
                      struct.pack(">H", 0)
                      + bytes(ip_parts)
                      + bytes([255, 255, 255, 0])
                      + bytes(ip_parts[:3] + [254]))
    blocks = devid_block + role_block + opts_block + name_block + ip_block
    xid_bytes = struct.pack(">I", xid)
    # ServiceID=5, ServiceType=1 (response, success)
    pnio_cm = struct.pack(">BBIHH", 5, 1, xid, 0, len(blocks)) + blocks
    return struct.pack(">H", 0xFEFF) + pnio_cm
