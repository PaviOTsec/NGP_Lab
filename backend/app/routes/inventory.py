"""Inventory + discovery + reachability → the dashboard's TargetViews."""

from __future__ import annotations

import asyncio

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core import hyperv, inventory_edit
from app.core.probe import probe_target
from app.deps import require_ready, verify_token
from app.models.api import CheckpointInfo, TargetView
from app.models.inventory import Target
from app.transports.base import TransportError

router = APIRouter(prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(verify_token)])


class SourceText(BaseModel):
    text: str
    base_sha256: str = ""


def _base_view(t: Target) -> TargetView:
    return TargetView(
        name=t.name,
        kind=t.kind,
        os=t.os,
        segment=t.segment,
        address=t.address,
        route=t.route,
        access=t.access,
        configured=t.configured,
        web_ui=t.web_ui,
        vendor=t.vendor,
        tags=t.tags,
        ot=t.ot,
    )


@router.get("/targets", response_model=list[TargetView])
async def targets(session=Depends(require_ready)) -> list[TargetView]:
    """All targets with inventory data + current session status + a fresh reachability probe."""
    inv = session.inventory
    pool = session.pool
    views = [_base_view(t) for t in inv.all()]

    # attach session status
    for v in views:
        v.session = pool.status_for(v.name)

    # reachability in parallel
    probes = await asyncio.gather(*(probe_target(t) for t in inv.all()))
    for v, r in zip(views, probes):
        v.reachability = r
    return views


@router.post("/discover", response_model=list[TargetView])
async def discover(session=Depends(require_ready)) -> list[TargetView]:
    """Merge live Get-VM data from each hypervisor into the target views."""
    inv = session.inventory
    pool = session.pool
    views = {t.name: _base_view(t) for t in inv.all()}

    async def one_host(host: Target) -> None:
        try:
            transport = await pool.hypervisor_shell(host.name)
            vms = await hyperv.get_vms(transport)
        except Exception:  # noqa: BLE001 - a dead host must not fail the whole discovery
            return
        by_vm = {vm.name: vm for vm in vms}
        for t in inv.targets:
            if t.host == host.name and t.vm_name in by_vm:
                vm = by_vm[t.vm_name]
                v = views[t.name]
                v.power_state = vm.state
                v.uptime_seconds = vm.uptime_seconds

    await asyncio.gather(*(one_host(h) for h in inv.hypervisors))

    for v in views.values():
        v.session = pool.status_for(v.name)
    return list(views.values())


@router.get("/source")
def source(session=Depends(require_ready)) -> dict:
    """inventory.yaml as text for the in-app editor (raw decode: no newline translation)."""
    path = session.settings.inventory_path
    text = path.read_bytes().decode("utf-8")
    return {"path": str(path), "text": text, "sha256": inventory_edit.sha256(text)}


@router.post("/validate")
def validate(body: SourceText, session=Depends(require_ready)) -> dict:
    return asdict(inventory_edit.review(session.inventory, body.text))


@router.put("/source")
async def save_source(body: SourceText, session=Depends(require_ready)) -> dict:
    """Validate, back up, write, then reload the inventory and re-warm sessions."""
    review = inventory_edit.review(session.inventory, body.text)
    if not review.ok:
        raise HTTPException(status_code=400, detail="; ".join(review.errors))
    path = session.settings.inventory_path
    try:
        backup = inventory_edit.write(path, body.text, body.base_sha256)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.audit.record(action="inventory-edit", target="-", result="ok",
                         detail={"added": review.added, "removed": review.removed,
                                 "changed": review.changed, "backup": backup.name})
    await session.load_credentials(session.credentials)
    statuses = await session.warm_up()
    return {**asdict(review), "backup": str(backup), "sessions": [s.model_dump() for s in statuses]}


@router.get("/checkpoints/{target_name}", response_model=list[CheckpointInfo])
async def checkpoints(target_name: str, session=Depends(require_ready)) -> list[CheckpointInfo]:
    inv = session.inventory
    t = inv.by_name(target_name)
    if t is None:
        return []
    try:
        transport = await session.pool.hypervisor_shell(target_name)
        snaps = await hyperv.list_checkpoints(transport, t.vm_name or t.name)
    except TransportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [CheckpointInfo(name=s.name, snapshot_type=s.snapshot_type) for s in snaps]
