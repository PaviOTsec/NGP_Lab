"""Inventory + discovery + reachability → the dashboard's TargetViews."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.core import hyperv
from app.core.probe import probe_target
from app.deps import require_ready, verify_token
from app.models.api import CheckpointInfo, TargetView
from app.models.inventory import Target
from app.transports.base import TransportError

router = APIRouter(prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(verify_token)])


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
