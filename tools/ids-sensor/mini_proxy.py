"""Temporary HTTP/HTTPS forward proxy on MC01 so the IDS VM can reach package repos during the build.

Accepts clients from ALLOWED only, supports CONNECT (HTTPS) and absolute-URI HTTP (apt over http),
logs every destination. Run it only while installing; it is not a service.

usage: python -I tools/ids-sensor/mini_proxy.py <bind-ip> <port> <allowed-client-ip>[,<ip>...]
"""
import asyncio
import sys
import time
from urllib.parse import urlsplit

BIND, PORT, ALLOWED = sys.argv[1], int(sys.argv[2]), set(sys.argv[3].split(","))


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


async def pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while data := await r.read(65536):
            w.write(data)
            await w.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        w.close()


async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
    peer = cw.get_extra_info("peername")[0]
    if peer not in ALLOWED:
        log(f"DENY client {peer}")
        cw.close()
        return
    try:
        head = await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"), 30)
        line, *hdrs = head.decode("latin-1").split("\r\n")
        method, target, ver = line.split(" ", 2)
        if method == "CONNECT":
            host, port = target.rsplit(":", 1)
            ur, uw = await asyncio.wait_for(asyncio.open_connection(host, int(port)), 20)
            cw.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await cw.drain()
            log(f"CONNECT {target}")
        else:
            u = urlsplit(target)
            host, port = u.hostname, u.port or 80
            path = (u.path or "/") + (f"?{u.query}" if u.query else "")
            keep = [h for h in hdrs if h and not h.lower().startswith(("proxy-", "connection:", "keep-alive:"))]
            ur, uw = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
            uw.write(f"{method} {path} {ver}\r\n".encode("latin-1")
                     + "".join(f"{h}\r\n" for h in keep).encode("latin-1") + b"Connection: close\r\n\r\n")
            await uw.drain()
            log(f"{method} http://{host}:{port}{path}")
        await asyncio.gather(pipe(cr, uw), pipe(ur, cw))
    except Exception as exc:  # noqa: BLE001 - one bad request must not kill the proxy
        log(f"ERROR {peer}: {exc!r}")
        try:
            cw.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            cw.close()
        except Exception:  # noqa: BLE001
            pass


async def main() -> None:
    srv = await asyncio.start_server(handle, BIND, PORT)
    log(f"proxy on {BIND}:{PORT}, clients {sorted(ALLOWED)}")
    async with srv:
        await srv.serve_forever()


asyncio.run(main())
