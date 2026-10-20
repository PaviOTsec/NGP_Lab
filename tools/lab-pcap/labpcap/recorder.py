"""Loopback recorder: real protocol stacks talk through it; it keeps the exact bytes.

Every emulated server binds 127.0.0.1 only — nothing is ever exposed on MC01's lab NICs.
"""
from __future__ import annotations

import socket
import threading
import time

LOOPBACK = "127.0.0.1"


def free_port() -> int:
    with socket.socket() as s:
        s.bind((LOOPBACK, 0))
        return s.getsockname()[1]


class TcpRecorder:
    """Accepts one client on `listen_port`, relays to `target_port`, records chunks.

    chunks: list of (direction, bytes) with direction 'c2s' or 's2c', in arrival order.
    """

    def __init__(self, target_port: int) -> None:
        self.target_port = target_port
        self.listen_port = free_port()
        self._chunks: list[tuple[str, bytes]] = []
        self._lock = threading.Lock()
        self._last = time.monotonic()
        self._lsock = socket.socket()
        self._lsock.bind((LOOPBACK, self.listen_port))
        self._lsock.listen(4)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                c, _ = self._lsock.accept()
            except OSError:
                return
            s = socket.create_connection((LOOPBACK, self.target_port))
            for sock in (c, s):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=self._pump, args=(c, s, "c2s"), daemon=True).start()
            threading.Thread(target=self._pump, args=(s, c, "s2c"), daemon=True).start()

    def _pump(self, a: socket.socket, b: socket.socket, direction: str) -> None:
        try:
            while True:
                data = a.recv(65536)
                if not data:
                    # Half-close only — let the peer finish sending any outstanding reply
                    try:
                        b.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    return
                with self._lock:
                    self._chunks.append((direction, data))
                    self._last = time.monotonic()
                try:
                    b.sendall(data)
                except OSError:
                    return
        except OSError:
            pass

    def take(self, settle: float = 0.08, timeout: float = 5.0) -> list[tuple[str, bytes]]:
        """Wait until the conversation is quiet for `settle` s, then return and clear chunks."""
        t0 = time.monotonic()
        while True:
            time.sleep(0.01)
            with self._lock:
                quiet = time.monotonic() - self._last >= settle
                if (quiet and self._chunks) or time.monotonic() - t0 > timeout:
                    out, self._chunks = self._chunks, []
                    return out

    def close(self) -> None:
        self._lsock.close()
