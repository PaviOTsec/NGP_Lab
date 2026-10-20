"""Credential-free host identity: ask a Windows host who it is BEFORE sending any login.

An NTLM handshake starts with the client's NEGOTIATE; the server answers with a CHALLENGE
that carries its NetBIOS computer name, domain, and DNS names (the target-info AV pairs).
We send only the NEGOTIATE — no username, no password, no response — read the CHALLENGE,
and stop. The connection is then dropped, so no logon is attempted and nothing is logged
as a failed logon on the target.

Why: inventory IPs come from drawings, and drawings drift. On 2026-10-09 the drawing's
"DMZ-HOST-2" address turned out to be L2-HOST-1 and "L3-HOST-1" was an L2 bare-metal box.
The pool calls `verify_identity` before every WinRM login so credentials are never sent to
the wrong machine.
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass

import httpx

from app.transports.base import TransportError

# NEGOTIATE flags: UNICODE | OEM | REQUEST_TARGET | NTLM | ALWAYS_SIGN | EXTENDED_SESSIONSECURITY
#                  | TARGET_INFO | VERSION | 128 | KEY_EXCH | 56
_FLAGS = 0xE2088297
_NEGOTIATE = b"NTLMSSP\x00" + struct.pack("<II", 1, _FLAGS) + b"\x00" * 16 + b"\x06\x01\xb1\x1d\x00\x00\x00\x0f"


class IdentityMismatch(TransportError):
    """The host at this address is not the machine the inventory says it is."""


@dataclass
class HostIdentity:
    computer: str = ""  # NetBIOS computer name, e.g. DMZ-HOST-1
    domain: str = ""  # NetBIOS domain/workgroup name (equals computer on workgroup hosts)
    dns_computer: str = ""  # e.g. DMZH2DC.np.local
    dns_domain: str = ""  # e.g. np.local

    @property
    def domain_joined(self) -> bool:
        return bool(self.domain) and self.domain.upper() != self.computer.upper()


def parse_challenge(blob: bytes) -> HostIdentity:
    if not blob.startswith(b"NTLMSSP\x00") or struct.unpack_from("<I", blob, 8)[0] != 2:
        raise TransportError("not an NTLM CHALLENGE message")
    ti_len, _, ti_off = struct.unpack_from("<HHI", blob, 40)
    info = blob[ti_off: ti_off + ti_len]
    ident = HostIdentity()
    fields = {1: "computer", 2: "domain", 3: "dns_computer", 4: "dns_domain"}
    pos = 0
    while pos + 4 <= len(info):
        av_id, av_len = struct.unpack_from("<HH", info, pos)
        pos += 4
        if av_id == 0:  # MsvAvEOL
            break
        if av_id in fields:
            setattr(ident, fields[av_id], info[pos: pos + av_len].decode("utf-16-le", "replace"))
        pos += av_len
    return ident


async def probe_identity(address: str, port: int = 5985, timeout: float = 5.0) -> HostIdentity:
    """Who is listening on WinRM at this address? Sends no credentials."""
    url = f"http://{address}:{port}/wsman"
    headers = {"Authorization": "Negotiate " + base64.b64encode(_NEGOTIATE).decode(),
               "Content-Type": "application/soap+xml;charset=UTF-8", "Content-Length": "0"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers)
    except (httpx.HTTPError, OSError) as exc:
        raise TransportError(f"identity probe failed on {address}:{port}: {type(exc).__name__}") from exc
    for value in resp.headers.get_list("www-authenticate"):
        scheme, _, token = value.partition(" ")
        if scheme.lower() in ("negotiate", "ntlm") and token:
            return parse_challenge(base64.b64decode(token))
    raise TransportError(f"{address}:{port} did not return an NTLM challenge (status {resp.status_code})")


def check(expected: str, ident: HostIdentity, address: str) -> None:
    """Raise unless the host's NetBIOS (or DNS short) name equals `expected` (case-insensitive)."""
    names = {ident.computer.upper(), ident.dns_computer.split(".")[0].upper()} - {""}
    if expected.upper() not in names:
        raise IdentityMismatch(
            f"identity mismatch at {address}: host says it is {ident.computer or '?'}"
            f" ({ident.dns_computer or 'no DNS name'}), inventory expects {expected}. "
            "No credentials were sent."
        )
