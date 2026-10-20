import asyncio, sys, yaml
from pathlib import Path
from pysnmp.hlapi.v3arch.asyncio import (SnmpEngine, UsmUserData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, get_cmd, usmHMAC192SHA256AuthProtocol, usmHMACSHAAuthProtocol, usmAesCfb128Protocol)
creds = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["credentials"]
auth, priv = creds["snmpv3/nms"]["password"], creds["snmpv3/nms-priv"]["password"]
proto = {"sha256": usmHMAC192SHA256AuthProtocol, "sha": usmHMACSHAAuthProtocol}[sys.argv[3]]
async def main():
    for label, a in (("correct credentials", auth), ("WRONG auth password (negative test)", auth[::-1])):
        err, status, idx, binds = await get_cmd(SnmpEngine(), UsmUserData("sinecnms", a, priv, authProtocol=proto, privProtocol=usmAesCfb128Protocol),
            await UdpTransportTarget.create((sys.argv[2], 161), timeout=3, retries=1), ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")), ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")))
        print(f"{label}: ", "ERROR " + str(err) if err else " ; ".join(f"{b[0].prettyPrint()} = {b[1].prettyPrint()[:70]}" for b in binds))
asyncio.run(main())
