import asyncio, sys
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, get_cmd
async def main():
    err, st, idx, binds = await get_cmd(SnmpEngine(), CommunityData("public", mpModel=1),
        await UdpTransportTarget.create((sys.argv[1], 161), timeout=2, retries=1), ContextData(), ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")))
    print("v2c 'public':", "REFUSED/" + str(err) if err else "ANSWERED " + binds[0][1].prettyPrint()[:60])
asyncio.run(main())
