"""Fan-out: run one command across many targets in parallel over their warm sessions."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.deps import require_ready, verify_token
from app.models.api import FanoutRequest, FanoutResult, TransportName
from app.transports.base import TransportError

router = APIRouter(prefix="/api/fanout", tags=["fanout"], dependencies=[Depends(verify_token)])


@router.post("", response_model=list[FanoutResult])
async def fanout(body: FanoutRequest, session=Depends(require_ready)) -> list[FanoutResult]:
    pool = session.pool
    audit = session.audit

    async def run_one(name: str) -> FanoutResult:
        try:
            transport = await pool.shell(name)
            result = await transport.run(body.command, timeout=body.timeout_seconds)
            audit.record(
                action="fanout",
                target=name,
                transport=transport.name,
                result="ok" if result.exit_code in (0, None) else "nonzero",
                detail={"exit_code": result.exit_code, "duration_ms": result.duration_ms},
            )
            return FanoutResult(
                target=name,
                transport=transport.name,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=result.duration_ms,
            )
        except TransportError as exc:
            audit.record(action="fanout", target=name, result="error", detail={"error": str(exc)})
            return FanoutResult(
                target=name,
                transport=TransportName.NONE,
                exit_code=None,
                stdout="",
                stderr="",
                duration_ms=0,
                error=str(exc),
            )

    return list(await asyncio.gather(*(run_one(n) for n in body.targets)))
