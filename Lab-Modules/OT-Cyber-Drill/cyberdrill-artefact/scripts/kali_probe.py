"""First-contact read-only probe of the drill Kali over SSH: capture + pin the host key, confirm
reach, and inventory the attacker tooling. usage: python -I kali_probe.py"""
import asyncio
import base64
import hashlib
import sys

sys.path.insert(0, "backend")
import asyncssh  # noqa: E402

HOST = "10.5.20.50"
USER = "kali"
PW = "kali"

CMDS = [
    ("whoami", "whoami"),
    ("id", "id"),
    ("hostname", "hostname -f"),
    ("ip", "ip -4 -o addr show eth0"),
    ("route", "ip route | head -5"),
    ("uname", "uname -a"),
    ("os", "grep PRETTY_NAME /etc/os-release"),
    ("nmap", "command -v nmap && nmap --version | head -1"),
    ("nxc", "command -v nxc netexec crackmapexec 2>/dev/null"),
    ("impacket", "command -v impacket-secretsdump impacket-psexec 2>/dev/null; python3 -c 'import impacket,sys; print(\"impacket\", impacket.__version__)' 2>/dev/null"),
    ("responder", "command -v responder Responder 2>/dev/null"),
    ("evilwinrm", "command -v evil-winrm 2>/dev/null"),
    ("python", "python3 --version"),
]


def fp(key: "asyncssh.SSHKey") -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.public_data).digest()).decode().rstrip("=")


async def main() -> None:
    # known_hosts=None: first contact, no prior pin. We capture the key and pin it ourselves.
    async with asyncssh.connect(HOST, username=USER, password=PW, known_hosts=None) as conn:
        hk = conn.get_server_host_key()
        print("HOST KEY TYPE :", hk.get_algorithm())
        print("FINGERPRINT   :", fp(hk))
        print("-" * 50)
        for label, cmd in CMDS:
            r = await conn.run(cmd, check=False)
            out = (r.stdout or "").strip() or (r.stderr or "").strip() or "(none)"
            print(f"{label:10}: {out}")


asyncio.run(main())
