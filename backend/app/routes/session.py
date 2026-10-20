"""Credentials load / unload / status routes.

The operator chooses the credentials file in the app: either uploads it from the browser
(file picker) or names a path on MC01 (remembered for next launch).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, ValidationError

from app.core.credentials import CredentialsError, CredentialStore
from app.deps import get_session, get_state, require_ready, verify_token
from app.models.api import SessionStatus

router = APIRouter(prefix="/api/session", tags=["session"], dependencies=[Depends(verify_token)])


class LoadPathRequest(BaseModel):
    path: str
    remember: bool = True


@router.get("/state")
def state(request: Request) -> dict:
    st = get_state(request)
    session = st.session
    cs = st.settings.clipboard_server
    return {
        "ready": session.ready,
        "credentials_source": session.credentials_source,
        "last_credentials_path": session.remembered().get("last_credentials_path", ""),
        "inventory_path": str(st.settings.inventory_path),
        "inventory_exists": st.settings.inventory_path.exists(),
        "clipboard_port": cs.port if cs.enabled else None,
    }


async def _load(request: Request, store: CredentialStore, remember_path: str = "") -> dict:
    session = get_session(request)
    try:
        await session.load_credentials(store, remember_path=remember_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"inventory not found: {exc.filename} — copy config/inventory.example.yaml",
        ) from exc
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"inventory is invalid: {exc}") from exc
    statuses = await session.warm_up()
    return {"ready": True, "credentials_source": store.source,
            "entries": len(store.names()), "sessions": [s.model_dump() for s in statuses]}


@router.post("/load-file")
async def load_file(request: Request, file: UploadFile) -> dict:
    """Credentials uploaded from the browser's file picker."""
    raw = await file.read()
    try:
        store = CredentialStore.parse(raw.decode("utf-8-sig"), source=file.filename or "uploaded")
    except (CredentialsError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _load(request, store)


@router.post("/load-path")
async def load_path(request: Request, body: LoadPathRequest) -> dict:
    """Credentials read from a path on MC01."""
    try:
        store = CredentialStore.load(body.path)
    except CredentialsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _load(request, store, remember_path=body.path if body.remember else "")


@router.post("/unload")
async def unload(request: Request) -> dict:
    await get_session(request).unload("manual")
    return {"ready": False}


@router.post("/reconnect")
async def reconnect(session=Depends(require_ready)) -> list[SessionStatus]:
    """Re-run the warm-up (picks up targets that were down at load)."""
    return await session.warm_up()


@router.get("/sessions", response_model=list[SessionStatus])
def sessions(session=Depends(require_ready)) -> list[SessionStatus]:
    return session.pool.statuses()
