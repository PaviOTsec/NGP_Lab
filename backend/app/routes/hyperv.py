"""Hyper-V power and checkpoint routes. All verification lives in app.core.hyperv."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException

from app.core import hyperv
from app.deps import require_ready, verify_token
from app.models.api import CheckpointRequest, GroupRestoreRequest, HyperVActionRequest
from app.transports.base import Transport, TransportError

router = APIRouter(prefix="/api/hyperv", tags=["hyperv"], dependencies=[Depends(verify_token)])

T = TypeVar("T")


async def _on_host(session, target_name: str, action: str, fn: Callable[[Transport, str], Awaitable[T]],
                   detail: dict | None = None) -> tuple[T, Transport]:
    """Run `fn(host_transport, vm_name)` and audit failures; errors become HTTP 400."""
    t = session.inventory.by_name(target_name)
    if t is None:
        raise HTTPException(status_code=404, detail=f"unknown target: {target_name}")
    try:
        transport = await session.pool.hypervisor_shell(target_name)
        result = await fn(transport, t.vm_name or t.name)
    except TransportError as exc:
        session.audit.record(action=action, target=target_name, result="error",
                             detail={**(detail or {}), "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result, transport


@router.post("/power")
async def power(body: HyperVActionRequest, session=Depends(require_ready)) -> dict:
    state, tr = await _on_host(session, body.target, f"power:{body.action}",
                               lambda h, vm: hyperv.set_power(h, vm, body.action))
    session.audit.record(action=f"power:{body.action}", target=body.target, transport=tr.name,
                         result=state.state)
    return {"target": body.target, "state": state.state}


@router.post("/checkpoint")
async def checkpoint(body: CheckpointRequest, session=Depends(require_ready)) -> dict:
    snap, tr = await _on_host(
        session, body.target, "checkpoint",
        lambda h, vm: hyperv.create_checkpoint(h, vm, checkpoint_type=body.checkpoint_type,
                                               name=body.name),
        detail={"requested_type": body.checkpoint_type},
    )
    session.audit.record(action="checkpoint", target=body.target, transport=tr.name, result="ok",
                         detail={"snapshot": snap.name, "type": snap.snapshot_type})
    return {"target": body.target, "name": snap.name, "snapshot_type": snap.snapshot_type}


@router.get("/vss/{target_name}")
async def vss(target_name: str, session=Depends(require_ready)) -> dict:
    """Whether a Production checkpoint is safe to offer for this VM."""
    try:
        healthy, _ = await _on_host(session, target_name, "vss-check", hyperv.vss_healthy)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise
        healthy = False
    return {"target": target_name, "vss_healthy": healthy}


@router.post("/restore")
async def restore(body: HyperVActionRequest, session=Depends(require_ready)) -> dict:
    if not body.checkpoint_name:
        raise HTTPException(status_code=400, detail="checkpoint_name is required")
    name = body.checkpoint_name
    state, tr = await _on_host(session, body.target, "restore",
                               lambda h, vm: hyperv.restore_checkpoint(h, vm, name),
                               detail={"checkpoint": name})
    session.audit.record(action="restore", target=body.target, transport=tr.name,
                         result=state.state, detail={"checkpoint": name})
    return {"target": body.target, "state": state.state}


@router.post("/delete-checkpoint")
async def delete_checkpoint(body: HyperVActionRequest, session=Depends(require_ready)) -> dict:
    if not body.checkpoint_name:
        raise HTTPException(status_code=400, detail="checkpoint_name is required")
    name = body.checkpoint_name
    _, tr = await _on_host(session, body.target, "delete-checkpoint",
                           lambda h, vm: hyperv.delete_checkpoint(h, vm, name),
                           detail={"checkpoint": name})
    session.audit.record(action="delete-checkpoint", target=body.target, transport=tr.name,
                         result="ok", detail={"checkpoint": name})
    return {"target": body.target, "deleted": name}


@router.post("/group-restore")
async def group_restore(body: GroupRestoreRequest, session=Depends(require_ready)) -> list[dict]:
    """FR-19: restore a named group of VMs to a named checkpoint in one action (training reset)."""
    async def one(name: str) -> dict:
        try:
            state, tr = await _on_host(
                session, name, "group-restore",
                lambda h, vm: hyperv.restore_checkpoint(h, vm, body.checkpoint_name),
                detail={"checkpoint": body.checkpoint_name},
            )
        except HTTPException as exc:
            return {"target": name, "error": exc.detail}
        session.audit.record(action="group-restore", target=name, transport=tr.name,
                             result=state.state, detail={"checkpoint": body.checkpoint_name})
        return {"target": name, "state": state.state}

    return list(await asyncio.gather(*(one(n) for n in body.targets)))
