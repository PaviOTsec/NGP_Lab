"""Run a local script (python3 or bash) on the drill Kali over SSH (host key pinned), print output.
The working tool for building the Red side on Kali. usage: python -I kali_run.py <localfile> [python3|bash]"""
import asyncio, sys, hashlib, base64
sys.path.insert(0, "backend")
import asyncssh  # noqa: E402

KALI, PIN = "10.5.20.50", "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"


async def main() -> None:
    local = sys.argv[1]
    interp = sys.argv[2] if len(sys.argv) > 2 else "python3"
    script = open(local, "r", encoding="utf-8").read()
    async with asyncssh.connect(KALI, username="kali", password="kali", known_hosts=None) as c:
        key = c.get_server_host_key()
        got = "SHA256:" + base64.b64encode(hashlib.sha256(key.public_data).digest()).decode().rstrip("=")
        assert got == PIN, f"HOST KEY MISMATCH {got}"
        r = await c.run(f"{interp} -", input=script, check=False)
        sys.stdout.write(r.stdout or "")
        if r.stderr:
            sys.stdout.write("\n[stderr]\n" + r.stderr)


asyncio.run(main())
