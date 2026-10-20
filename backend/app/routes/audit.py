"""Audit log viewer route. Available before credentials are loaded."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.deps import get_session, verify_token

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(verify_token)])


@router.get("")
def recent(request: Request, limit: int = 200) -> dict:
    return {"events": get_session(request).audit.tail(limit)}
