"""Pre-auth probe (no credentials sent): TCP 22/443 reachability, SSH host key + banner, TLS cert
fingerprint and WBM page title. For first contact with devices outside the inventory.
usage: python -I preauth_probe.py <backend_dir> <name=ip> ..."""
import asyncio
import hashlib
import re
import socket
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
import asyncssh  # noqa: E402

DEVICES = [a.split("=", 1) for a in sys.argv[2:]]


def tcp_open(ip: str, port: int) -> bool:
    try:
        socket.create_connection((ip, port), 4).close()
        return True
    except OSError:
        return False


def tls_info(ip: str) -> str:
    c = ssl.create_default_context()
    c.check_hostname, c.verify_mode = False, ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((ip, 443), 5)) as s:
        fp = "SHA256:" + hashlib.sha256(s.getpeercert(True)).hexdigest().upper()
        s.sendall(f"GET / HTTP/1.0\r\nHost: {ip}\r\n\r\n".encode())
        data = b""
        while len(data) < 200000:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    title = re.search(rb"(?is)<title>(.*?)</title>", data)
    return f"tls={fp} title={title.group(1).decode(errors='replace').strip() if title else '-'}"


async def ssh_key(ip: str) -> str:
    key = await asyncio.wait_for(asyncssh.get_server_host_key(ip, 22), 10)
    return f"ssh={key.get_fingerprint()} ({key.get_algorithm()})"


async def main() -> None:
    for name, ip in DEVICES:
        p22, p443 = tcp_open(ip, 22), tcp_open(ip, 443)
        parts = [f"{name:8} {ip:15} 22={'open' if p22 else 'closed'} 443={'open' if p443 else 'closed'}"]
        if p22:
            try:
                parts.append(await ssh_key(ip))
            except Exception as e:  # noqa: BLE001
                parts.append(f"ssh-key-error={type(e).__name__}")
        if p443:
            try:
                parts.append(tls_info(ip))
            except Exception as e:  # noqa: BLE001
                parts.append(f"tls-error={type(e).__name__}")
        print("  ".join(parts))


asyncio.run(main())
