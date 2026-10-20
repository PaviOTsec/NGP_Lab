"""Read-only: from Kali, check the NMS host (MaintServer, L3) is reachable on the ports PtH needs."""
import asyncio, sys, hashlib, base64
sys.path.insert(0, "backend")
import asyncssh  # noqa: E402

HOST = "10.5.20.50"
PIN = "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"


async def main() -> None:
    async with asyncssh.connect(HOST, username="kali", password="kali", known_hosts=None) as conn:
        key = conn.get_server_host_key()
        got = "SHA256:" + base64.b64encode(hashlib.sha256(key.public_data).digest()).decode().rstrip("=")
        assert got == PIN, f"HOST KEY MISMATCH {got}"
        print("host key OK\n")
        r = await conn.run("nmap -Pn -n --open -p445,3389,5985,443,8443 192.168.30.11 | grep -E '^[0-9]+/tcp|Nmap scan'", check=False)
        print("--- MaintServer / NMS 192.168.30.11")
        print((r.stdout or r.stderr or "(none)").strip())


asyncio.run(main())
