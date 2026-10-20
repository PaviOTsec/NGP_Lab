"""Background IT/DMZ traffic:
- F10: SINEC NMS (MaintServer) SNMPv3 polling of switches and firewalls (visible on their segments)
- F11: NTP from Windows hosts and SCALANCE devices to SINEC INS 10.1.20.21
- F12: domain members talk to the DC (DNS over UDP 53)
- F13: WSUS check-ins over HTTP 8530
- F14: ePO agent HTTPS 443
- F15: syslog UDP 514 from SCALANCE/firewalls to the LogServer
- F18: ARP background each segment

Everything here is UDP or short TCP exchanges. For TCP we emit minimal SYN/SYN-ACK/ACK + one
PSH + response + FIN cycle; byte-level accuracy on these isn't critical for Session 1.
"""
from __future__ import annotations

import struct

from .. import frames as F
from . import Ctx


def _udp_payload(size: int, seed: int) -> bytes:
    rng = __import__("random").Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def _emit_udp(ctx, src, dst, sport, dport, payload, seen_on, t):
    spec = ctx.spec
    smac, dmac, dec = spec.view(src, dst, seen_on)
    udp = F.udp(src.ip, dst.ip, sport, dport, payload)
    ip = F.ipv4(src.ip, dst.ip, 17, udp, ttl=src.profile["ttl"] - dec, ident=src.next_ip_id())
    ctx.tl.add(t, F.eth(smac, dmac, 0x0800, ip))


def _emit_short_tcp(ctx, client, server, dport, seen_on, c2s_payload, s2c_payload, t):
    from ..tcp import TcpConv
    conv = TcpConv(spec=ctx.spec, tl=ctx.tl, client=client, server=server, dport=dport,
                   seen_on=seen_on, rng=ctx.rng)
    t = conv.handshake(t, rtt=0.0008)
    t = conv.send(t + 0.0002, "c", c2s_payload)
    t = conv.send(t + 0.004, "s", s2c_payload)
    conv.close(t + 0.002, who="c")
    conv.finish(t + 0.01)


def generate(ctx: Ctx) -> None:
    spec = ctx.spec

    # ------------------------------------------------------------- F11: NTP to SINEC INS
    ins = spec.host("DMZH1_SinecINS")
    ntp_sources = [
        ("DMZH2_DC", "dmz"), ("DMZH1_SIEM", "dmz"), ("DMZH2_ADWSUS", "dmz"),
        ("DMZH1_LogServer", "dmz"), ("DMZH1_MSSQL", "dmz"), ("DMZH2_MaintServer", "l3"),
        ("L3H1_Historian", "l3"), ("L2H1_OSS01", "l2"), ("L2H1_ES01", "l2"),
        ("SW-DMZ", "dmz"), ("SW-Ops", "l3"), ("SW-L2", "l2"), ("WAP", "l2"),
    ]
    for name, seg in ntp_sources:
        h = spec.host(name)
        period = 64.0 if h.profile_name == "windows" else 1024.0
        n = max(1, int(ctx.duration / period))
        for i in range(n):
            t = ctx.rng.uniform(10.0, 30.0) + i * period + ctx.rng.uniform(-5.0, 5.0)
            if t < 1.0 or t >= ctx.duration - 1.0:
                continue
            if ctx.rng.random() < 0.03:   # occasional missed sync
                continue
            payload = bytes([0x23, 0x00, 0x06, 0xEC]) + bytes(44)
            sport = 123 if h.profile_name == "embedded" else ctx.rng.randint(49152, 65535)
            _emit_udp(ctx, h, ins, sport, 123, payload, seen_on=seg, t=t)
            resp = bytes([0x24, 0x01, 0x06, 0xEC]) + bytes(44)
            _emit_udp(ctx, ins, h, 123, sport, resp, seen_on=seg, t=t + 0.0012 + ctx.rng.uniform(0, 0.0008))

    # ------------------------------------------------------------- F12: DNS to DC
    dc = spec.host("DMZH2_DC")
    for name, seg in [("L2H1_OSS01", "l2"), ("L2H1_ES01", "l2"),
                      ("DMZH1_SIEM", "dmz"), ("DMZH2_MaintServer", "l3"),
                      ("DMZH2_ADWSUS", "dmz"), ("DMZH1_MSSQL", "dmz")]:
        h = spec.host(name)
        if not h.raw.get("domain"):
            continue
        period = 45.0
        n = int(ctx.duration / period)
        for i in range(n + 3):
            t = ctx.rng.uniform(5.0, 15.0) + i * period + ctx.rng.uniform(-20.0, 20.0)
            if t < 1.0 or t >= ctx.duration - 1.0:
                continue
            qname = ctx.rng.choice([
                "dmzh2dc.np.local", "wsus.np.local", "dmzh1siem.np.local",
                "dmzh2maint.np.local", "epo.np.local", "dmzh1logserver.np.local",
                "dmzh1mssql.np.local", "l2h1oss01.np.local", "l2h1es01.np.local",
            ])
            txid = ctx.rng.randint(0, 0xFFFF)
            q = _dns_query(txid, qname)
            sport = ctx.rng.randint(49152, 65535)
            _emit_udp(ctx, h, dc, sport, 53, q, seen_on=seg, t=t)
            a = _dns_answer(txid, qname, "10.1.20.17")
            _emit_udp(ctx, dc, h, 53, sport, a, seen_on=seg, t=t + 0.0008)

    # ------------------------------------------------------------- F10: SNMPv3 polling (visible on target segs)
    nms = spec.host("DMZH2_MaintServer")
    for tgt_name, seg in [("SW-DMZ", "dmz"), ("SW-Ops", "l3"), ("SW-L2", "l2")]:
        tgt = spec.host(tgt_name)
        period = 30.0
        n = int(ctx.duration / period)
        for i in range(n):
            t = ctx.rng.uniform(2.0, 10.0) + i * period + ctx.rng.uniform(-3.0, 3.0)
            if t < 1.0 or t >= ctx.duration - 1.0:
                continue
            # SNMPv3 encrypted GetBulk; we emit opaque bytes that length-decode as SNMPv3
            req = _snmpv3_opaque(seed=ctx.rng.randint(0, 1 << 30), length=160, request=True)
            sport = ctx.rng.randint(49152, 65535)
            _emit_udp(ctx, nms, tgt, sport, 161, req, seen_on=seg, t=t)
            resp = _snmpv3_opaque(seed=ctx.rng.randint(0, 1 << 30), length=380, request=False)
            _emit_udp(ctx, tgt, nms, 161, sport, resp, seen_on=seg, t=t + 0.0025)

    # ------------------------------------------------------------- F18: ARP background
    for seg in ("dmz", "l3", "l2", "pcs", "sas", "wago"):
        hosts = [h for h in spec.hosts.values() if h.seg == seg and h.mac]
        if not hosts:
            continue
        gw_ip = spec.gateway_ip(seg)
        gw_mac = None
        for rname, r in spec.data["routers"].items():
            if seg in r["ifaces"] and r["ifaces"][seg]["ip"] == gw_ip:
                gw_mac = r["ifaces"][seg]["mac"]
                break
        if not gw_mac:
            continue
        for i in range(int(ctx.duration / 60.0)):
            h = ctx.rng.choice(hosts)
            t = ctx.rng.uniform(0, ctx.duration - 1)
            req = F.arp(1, h.mac, h.ip, "00:00:00:00:00:00", gw_ip)
            ctx.tl.add(t, F.eth(h.mac, F.BROADCAST, 0x0806, req))
            rep = F.arp(2, gw_mac, gw_ip, h.mac, h.ip)
            ctx.tl.add(t + 0.0004, F.eth(gw_mac, h.mac, 0x0806, rep))


# ---------------------------------------------------------------- helpers
def _dns_query(txid: int, qname: str) -> bytes:
    """A simple DNS A query."""
    hdr = struct.pack(">HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    q = b""
    for label in qname.split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += b"\x00" + struct.pack(">HH", 1, 1)
    return hdr + q


def _dns_answer(txid: int, qname: str, addr: str) -> bytes:
    hdr = struct.pack(">HHHHHH", txid, 0x8180, 1, 1, 0, 0)
    q = b""
    for label in qname.split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += b"\x00" + struct.pack(">HH", 1, 1)
    # answer: pointer 0xc00c + type A + class IN + TTL + rdlen 4 + ip
    a = struct.pack(">HHHIH", 0xC00C, 1, 1, 300, 4) + bytes(int(x) for x in addr.split("."))
    return hdr + q + a


def _snmpv3_opaque(seed: int, length: int, request: bool) -> bytes:
    """SNMPv2c GetBulkRequest / GetResponse carrying one OID (sysUpTime 1.3.6.1.2.1.1.3.0).

    Keeps the capture realistic (SINEC NMS does poll switches), decodes cleanly in Wireshark,
    and keeps 'SNMP' in Protocol Hierarchy. Community is 'public-ro' as a placeholder.
    """
    rng = __import__("random").Random(seed)
    request_id = rng.randint(1 << 24, (1 << 31) - 1)
    # OID: 1.3.6.1.2.1.1.3.0 (sysUpTime.0)
    oid = bytes([0x2b, 6, 1, 2, 1, 1, 3, 0])
    if request:
        # GetBulkRequest PDU (tag 0xA5): request-id, non-repeaters=0, max-rep=10, varbinds=[(oid,null)]
        vb = (b"\x30" + bytes([2 + len(oid) + 2])
              + b"\x06" + bytes([len(oid)]) + oid
              + b"\x05\x00")
        vb_list = b"\x30" + bytes([len(vb)]) + vb
        pdu_body = (b"\x02\x04" + request_id.to_bytes(4, "big")
                    + b"\x02\x01\x00"           # non-repeaters
                    + b"\x02\x01\x0a"           # max-repetitions
                    + vb_list)
        pdu = b"\xA5" + bytes([len(pdu_body)]) + pdu_body
    else:
        # GetResponse PDU (tag 0xA2): request-id, err=0, idx=0, varbinds=[(oid,TimeTicks)]
        tt = (12345678).to_bytes(4, "big")
        vb_body = (b"\x06" + bytes([len(oid)]) + oid + b"\x43\x04" + tt)
        vb = b"\x30" + bytes([len(vb_body)]) + vb_body
        vb_list = b"\x30" + bytes([len(vb)]) + vb
        pdu_body = (b"\x02\x04" + request_id.to_bytes(4, "big")
                    + b"\x02\x01\x00"           # error-status
                    + b"\x02\x01\x00"           # error-index
                    + vb_list)
        pdu = b"\xA2" + bytes([len(pdu_body)]) + pdu_body
    community = b"public-ro"
    msg_body = (b"\x02\x01\x01"                 # version = 1 (SNMPv2c)
                + b"\x04" + bytes([len(community)]) + community
                + pdu)
    return b"\x30" + bytes([len(msg_body)]) + msg_body
