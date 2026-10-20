"""Read-only: from Kali, check the golden-path targets are reachable on the ports the drill needs.
Targeted host:port pairs only (no sweep). Pins the known host key. usage: python -I kali_reach.py"""
import asyncio
import sys

sys.path.insert(0, "backend")
import asyncssh  # noqa: E402

HOST = "10.5.20.50"
PIN = "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"
# named target : ports that matter for the golden path
TARGETS = {
    "10.5.20.10 (RAC, L5)": "445,3389,5985",
    "10.1.20.17 (DC, DMZ)": "88,389,445,3389",
    "10.1.20.14 (MSSQL, GP-0 seed)": "445,1433,3389",
    "10.1.20.21 (SINEC INS, GP-3)": "443,22",
}


async def main() -> None:
    import hashlib
    import base64

    def verify(key):
        got = "SHA256:" + base64.b64encode(hashlib.sha256(key.public_data).digest()).decode().rstrip("=")
        if got != PIN:
            raise SystemExit(f"HOST KEY MISMATCH: got {got} expected {PIN}")
        return True

    async with asyncssh.connect(HOST, username="kali", password="kali", known_hosts=None) as conn:
        verify(conn.get_server_host_key())
        print("host key OK (pinned)\n")
        for label, ports in TARGETS.items():
            ip = label.split()[0]
            r = await conn.run(f"nmap -Pn -n --open -p{ports} {ip} | grep -E '^[0-9]+/tcp|Nmap scan'", check=False)
            print(f"--- {label} : ports {ports}")
            print((r.stdout or r.stderr or "(no open ports)").strip())
            print()


asyncio.run(main())
