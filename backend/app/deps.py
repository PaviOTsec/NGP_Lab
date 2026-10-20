"""Shared application state and FastAPI dependencies.

A single AppSession lives on `app.state`. The launch token is minted at startup and required
on every console request (header or query param), which — together with the Host check —
blocks other web pages from driving the console via DNS rebinding. The VM-facing clipboard
server does NOT use the token; it only exposes the clipboard board.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from fastapi import Header, HTTPException, Request, status

from app.config import Settings
from app.core.clipstore import ClipStore
from app.core.session import AppSession, SessionNotReady
from app.playbooks.engine import PlaybookRegistry, RunManager


@dataclass
class AppState:
    settings: Settings
    session: AppSession
    clipstore: ClipStore
    playbooks: PlaybookRegistry
    runs: RunManager
    launch_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))


def get_state(request: Request) -> AppState:
    return request.app.state.appstate  # type: ignore[no-any-return]


def get_session(request: Request) -> AppSession:
    return get_state(request).session


def require_ready(request: Request) -> AppSession:
    """The operation needs loaded credentials (an inventory and a session pool)."""
    session = get_session(request)
    if not session.ready:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="no credentials loaded")
    return session


def token_ok(state: AppState, supplied: str | None) -> bool:
    return bool(supplied) and secrets.compare_digest(supplied, state.launch_token)


async def verify_token(
    request: Request,
    x_labconsole_token: str | None = Header(default=None),
) -> None:
    """Require the launch token on every call. Accept it in a header or ?token= query param."""
    supplied = x_labconsole_token or request.query_params.get("token")
    if not token_ok(get_state(request), supplied):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad or missing token")


__all__ = ["AppState", "get_state", "get_session", "require_ready", "verify_token", "token_ok",
           "SessionNotReady"]
