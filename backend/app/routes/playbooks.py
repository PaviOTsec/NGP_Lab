"""Playbook routes: list, run (background), watch progress, browse history and artifacts."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.deps import get_state, require_ready, verify_token

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"], dependencies=[Depends(verify_token)])


class RunRequest(BaseModel):
    name: str
    params: dict = Field(default_factory=dict)
    targets: list[str] | None = None  # override the playbook's selector with explicit names
    actor: str = "operator"  # who started it: operator | agent:<name>


@router.get("")
def list_playbooks(request: Request, session=Depends(require_ready)) -> dict:
    st = get_state(request)
    st.playbooks.reload()  # pick up edits/drop-ins each time the list is opened
    out = []
    for pb in st.playbooks.all():
        out.append({
            "name": pb.name,
            "title": pb.title,
            "description": pb.description,
            "confirm": pb.confirm,
            "params": [p.model_dump() for p in pb.params],
            "steps": [{"name": s.name, "module": s.module, "credential": s.credential}
                      for s in pb.steps],
            "matches": [t.name for t in st.playbooks.targets_for(pb, session.inventory)],
            "source_file": pb.source_file,
        })
    return {"playbooks": out, "errors": st.playbooks.errors}


@router.post("/run")
async def run_playbook(request: Request, body: RunRequest, session=Depends(require_ready)) -> dict:
    # async on purpose: the run is an asyncio task, so this must execute on the event loop
    # (a plain `def` route runs in a worker thread with no loop).
    st = get_state(request)
    pb = st.playbooks.get(body.name)
    if pb is None:
        raise HTTPException(status_code=404, detail=f"unknown playbook: {body.name}")
    if body.targets is not None:
        targets = []
        for name in body.targets:
            t = session.inventory.by_name(name)
            if t is None:
                raise HTTPException(status_code=404, detail=f"unknown target: {name}")
            targets.append(t)
    else:
        targets = st.playbooks.targets_for(pb, session.inventory)
    if not targets:
        raise HTTPException(status_code=400, detail="no targets match this playbook")
    try:
        run = st.runs.start(pb, pool=session.pool, targets=targets, params=body.params,
                            actor=body.actor)
    except ValueError as exc:  # bad parameter value
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run.summary()


@router.get("/runs")
def runs(request: Request, limit: int = 50) -> dict:
    return {"runs": get_state(request).runs.history(limit)}


@router.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str, since: int = 0) -> dict:
    """Full run record. `since` = last event seq seen; only newer events are returned."""
    mgr = get_state(request).runs
    live = mgr.get(run_id)
    if live is not None:
        return live.to_dict(events_since=since)
    data = mgr.load(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    data["events"] = [e for e in data.get("events", []) if e.get("seq", 0) > since]
    return data


@router.post("/runs/{run_id}/cancel")
def cancel(request: Request, run_id: str) -> dict:
    return {"cancelled": get_state(request).runs.cancel(run_id)}


@router.get("/runs/{run_id}/files/{rel_path:path}")
def run_file(request: Request, run_id: str, rel_path: str) -> FileResponse:
    """Download a step log or artifact from a run folder."""
    runs_dir = get_state(request).runs.runs_dir.resolve()
    path = (runs_dir / run_id / rel_path).resolve()
    if not path.is_relative_to(runs_dir / run_id) or not path.is_file():
        raise HTTPException(status_code=404, detail="no such file")
    return FileResponse(path, filename=Path(rel_path).name)
