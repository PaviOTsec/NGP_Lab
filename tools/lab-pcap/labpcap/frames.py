"""Raw Ethernet / IPv4 / UDP / ARP frame builders with correct checksums."""
from __future__ import annotations

import ipaddress
import struct


def mac_bytes(mac: str) -> bytes:
    return bytes(int(x, 16) for x in mac.split(":"))


def ip_bytes(ip: str) -> bytes:
    return ipaddress.ip_address(ip).packed


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def eth(src: str, dst: str, ethertype: int, payload: bytes) -> bytes:
    frame = mac_bytes(dst) + mac_bytes(src) + struct.pack("!H", ethertype) + payload
    return frame + b"\x00" * max(0, 60 - len(frame))   # SPAN copies show the padding (FCS stripped)


def ipv4(src: str, dst: str, proto: int, payload: bytes, ttl: int, ident: int, df: bool = True, tos: int = 0) -> bytes:
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, tos, 20 + len(payload), ident, 0x4000 if df else 0,
                      ttl, proto, 0, ip_bytes(src), ip_bytes(dst))
    hdr = hdr[:10] + struct.pack("!H", checksum(hdr)) + hdr[12:]
    return hdr + payload


def pseudo(src: str, dst: str, proto: int, length: int) -> bytes:
    return ip_bytes(src) + ip_bytes(dst) + struct.pack("!BBH", 0, proto, length)


def udp(src: str, dst: str, sport: int, dport: int, payload: bytes) -> bytes:
    hdr = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0)
    c = checksum(pseudo(src, dst, 17, 8 + len(payload)) + hdr + payload) or 0xFFFF
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), c) + payload


def arp(op: int, sha: str, spa: str, tha: str, tpa: str) -> bytes:
    return struct.pack("!HHBBH", 1, 0x0800, 6, 4, op) + mac_bytes(sha) + ip_bytes(spa) + mac_bytes(tha) + ip_bytes(tpa)


BROADCAST = "ff:ff:ff:ff:ff:ff"
