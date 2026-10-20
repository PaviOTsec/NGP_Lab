"""Read-only SNMPv3 walk of one or more subtrees with the NMS credentials (sinecnms, AES-128).
Used to check which LLDP MIB a device exposes (what SINEC NMS can read for topology).
usage: python -I snmpv3_walk.py <credentials.yaml> <ip> <sha256|sha> <oid> [<oid>...]
(needs a venv with pysnmp>=7 pycryptodomex cryptography pyyaml)"""
import asyncio, sys, yaml
from pathlib import Path
from pysnmp.hlapi.v3arch.asyncio import (SnmpEngine, UsmUserData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, walk_cmd, usmHMAC192SHA256AuthProtocol, usmHMACSHAAuthProtocol, usmAesCfb128Protocol)

creds = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["credentials"]
auth, priv = creds["snmpv3/nms"]["password"], creds["snmpv3/nms-priv"]["password"]
proto = {"sha256": usmHMAC192SHA256AuthProtocol, "sha": usmHMACSHAAuthProtocol}[sys.argv[3]]


async def main():
    eng = SnmpEngine()
    user = UsmUserData("sinecnms", auth, priv, authProtocol=proto, privProtocol=usmAesCfb128Protocol)
    target = await UdpTransportTarget.create((sys.argv[2], 161), timeout=3, retries=1)
    for oid in sys.argv[4:]:
        n = 0
        async for err, status, idx, binds in walk_cmd(eng, user, target, ContextData(),
                                                      ObjectType(ObjectIdentity(oid)), lexicographicMode=False):
            if err or status:
                print(f"{oid}: ERROR {err or status.prettyPrint()}"); break
            for name, val in binds:
                n += 1
                if n <= 40:
                    print(f"  {name.prettyPrint()} = {val.prettyPrint()[:80]}")
        print(f"{oid}: {n} values")


asyncio.run(main())
