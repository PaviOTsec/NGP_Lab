"""Terminal WebSocket.

The browser opens ws://127.0.0.1:PORT/api/terminals/ws/{target}?token=... and gets an
interactive shell on the target over its warm transport. The token is checked on the
handshake (WebSockets can't send custom headers from the browser, so the query param is used).

Interactive PTY behaviour differs by transport:
  * SSH (asyncssh): a real PTY — full interactivity, resize supported.
  * WinRM (pypsrp): PSRP has no PTY; this streams line-oriented command I/O instead. Good
    enough for running commands and reading output; not a full curses TTY. The UI labels a
    WinRM terminal as "line mode".

TODO(mc01): for a fuller Windows experience, consider launching the native console/RDP for
heavy interactive work; this WS terminal targets quick command work.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.deps import token_ok
from app.models.api import TransportName

router = APIRouter(prefix="/api/terminals", tags=["terminals"])


@router.websocket("/ws/{target}")
async def terminal_ws(websocket: WebSocket, target: str) -> None:
    state = websocket.app.state.appstate
    if not token_ok(state, websocket.query_params.get("token")):
        await websocket.close(code=4401)
        return
    session = state.session
    if not session.ready:
        await websocket.close(code=4423)  # no credentials loaded
        return

    await websocket.accept()
    t = session.inventory.by_name(target)
    if t is None:
        await websocket.send_json({"type": "error", "message": f"unknown target: {target}"})
        await websocket.close()
        return

    try:
        transport = await session.pool.shell(target)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"cannot open session: {exc}"})
        await websocket.close()
        return

    if transport.name == TransportName.SSH:
        await _ssh_pty(websocket, transport)
    else:
        await _line_mode(websocket, transport)


async def _ssh_pty(websocket: WebSocket, transport) -> None:
    """Full interactive PTY over asyncssh."""
    conn = transport._conn  # the live asyncssh connection owned by the pool
    proc = await conn.create_process(term_type="xterm-256color", encoding="utf-8")
    await websocket.send_json({"type": "ready", "mode": "pty"})

    async def pump_out() -> None:
        try:
            async for data in proc.stdout:
                await websocket.send_json({"type": "data", "data": data})
        except Exception:  # noqa: BLE001
            pass

    out_task = asyncio.create_task(pump_out())
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "data":
                proc.stdin.write(msg["data"])
            elif msg.get("type") == "resize":
                proc.change_terminal_size(msg.get("cols", 80), msg.get("rows", 24))
    except WebSocketDisconnect:
        pass
    finally:
        out_task.cancel()
        proc.close()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


async def _line_mode(websocket: WebSocket, transport) -> None:
    """Line-oriented command execution for PSRP (no PTY)."""
    await websocket.send_json({"type": "ready", "mode": "line"})
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") != "data":
                continue
            command = msg["data"].rstrip("\r\n")
            if not command:
                continue
            try:
                result = await transport.run(command)
            except Exception as exc:  # noqa: BLE001 - report and keep the terminal open
                await websocket.send_json({"type": "error", "message": str(exc)})
                await websocket.send_json({"type": "exit", "code": None, "ms": 0})
                continue
            if result.stdout:
                await websocket.send_json({"type": "data", "data": result.stdout + "\n"})
            if result.stderr:
                await websocket.send_json({"type": "data", "data": result.stderr + "\n"})
            await websocket.send_json(
                {"type": "exit", "code": result.exit_code, "ms": result.duration_ms}
            )
    except WebSocketDisconnect:
        pass
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
