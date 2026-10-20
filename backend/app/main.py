"""FastAPI application entry point — two listeners in one process.

  * Console   (settings.server, 127.0.0.1:8765 by default): full lab control. Requires the
    per-launch token on every route and the terminal WebSocket; checks the Host header when
    bound to loopback (anti-DNS-rebinding).
  * Clipboard (settings.clipboard_server, 0.0.0.0:8766 by default): the shared clipboard page
    the VMs open. Serves ONLY the clipboard board — nothing that can touch a host.

Both share one clipboard store and one audit log, so the console UI, playbooks, agents and
the VMs all see the same board.
"""

from __future__ import annotations

import asyncio
import os
import webbrowser
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings
from app.core.clipstore import ClipStore
from app.core.session import AppSession
from app.deps import AppState, verify_token
from app.playbooks.engine import PlaybookRegistry, RunManager
from app.routes import (
    audit_routes,
    board_routes,
    fanout_routes,
    files_routes,
    hyperv_routes,
    inventory_routes,
    playbooks_routes,
    session_routes,
    terminals_routes,
    vmtext_routes,
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


class HostCheckMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Host header isn't in the allowed set — anti-DNS-rebinding."""

    def __init__(self, app, allowed: set[str]) -> None:
        super().__init__(app)
        self.allowed = allowed

    async def dispatch(self, request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        if host and host not in self.allowed:
            return JSONResponse({"detail": "bad host"}, status_code=400)
        return await call_next(request)


def build_state(settings: Settings) -> AppState:
    session = AppSession(settings=settings)
    clipstore = ClipStore(
        settings.clipboard_dir,
        max_items=settings.clipboard.max_items_per_board,
        max_file_bytes=settings.clipboard.max_file_mb << 20,
    )
    builtin = Path(__file__).resolve().parent / "playbooks" / "builtin"
    user = settings.repo_root / "playbooks"
    registry = PlaybookRegistry([user, builtin], [user / "modules"])
    runs = RunManager(runs_dir=settings.runs_abs, audit=session.audit, clipstore=clipstore,
                      default_concurrency=settings.playbooks.default_concurrency)
    return AppState(settings=settings, session=session, clipstore=clipstore,
                    playbooks=registry, runs=runs)


def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    """The operator console."""
    settings = settings or Settings.load()
    state = state or build_state(settings)
    app = FastAPI(title="Lab Console", version="0.2.0", docs_url=None, redoc_url=None)

    if settings.server.host in LOOPBACK_HOSTS:
        allowed = set(LOOPBACK_HOSTS)
        if os.environ.get("LABCONSOLE_TESTING"):
            allowed.add("testserver")  # Starlette's in-process test client
        app.add_middleware(HostCheckMiddleware, allowed=allowed)

    app.state.appstate = state

    for module in (
        session_routes,
        inventory_routes,
        fanout_routes,
        files_routes,
        hyperv_routes,
        vmtext_routes,
        terminals_routes,
        playbooks_routes,
        audit_routes,
    ):
        app.include_router(module.router)
    app.include_router(board_routes.make_router(
        state.clipstore, state.session.audit,
        inline_text_bytes=settings.clipboard.inline_text_kb << 10,
        serve_page=False, dependencies=[Depends(verify_token)],
    ))

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "ready": state.session.ready}

    # Serve the built frontend if present (production). In dev, Vite serves it on :5173.
    dist = settings.repo_root / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


def create_clipboard_app(settings: Settings, state: AppState) -> FastAPI:
    """The VM-facing clipboard server: the board page and its API, nothing else."""
    app = FastAPI(title="Lab Clipboard", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.appstate = state
    app.include_router(board_routes.make_router(
        state.clipstore, state.session.audit,
        inline_text_bytes=settings.clipboard.inline_text_kb << 10,
        serve_page=True,
    ))
    return app


async def _serve(settings: Settings) -> None:
    import uvicorn

    state = build_state(settings)
    console = create_app(settings, state)
    servers = [uvicorn.Server(uvicorn.Config(
        console, host=settings.server.host, port=settings.server.port, log_level="info"))]
    cs = settings.clipboard_server
    if cs.enabled:
        servers.append(uvicorn.Server(uvicorn.Config(
            create_clipboard_app(settings, state), host=cs.host, port=cs.port, log_level="warning")))

    url = f"http://127.0.0.1:{settings.server.port}/?token={state.launch_token}"
    print("\n  Lab Console")
    print("  Open this URL (it carries your session token):\n")
    print(f"    {url}\n")
    if cs.enabled:
        print(f"  Shared clipboard for the VMs: http://<MC01 address>:{cs.port}/")
        print(f"  (Windows Firewall must allow inbound TCP {cs.port}; see README.)\n")
    if settings.server.open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    await asyncio.gather(*(s.serve() for s in servers))


def run() -> None:
    """Console-script entry point."""
    asyncio.run(_serve(Settings.load()))


if __name__ == "__main__":
    run()
