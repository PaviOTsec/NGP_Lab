"""Session-backed clipboard helpers (console only, token required).

  POST /api/vmtext/type   — type text or a credential's password into a VM's keyboard
  POST /api/vmtext/push   — deliver a clipboard-board item to a file on a target, converted
                            for the target OS (text) or byte-exact (files), checksum-verified
  POST /api/vmtext/pull   — read a file from a target and post it to a clipboard board
"""

from __future__ import annotations

import hashlib
import io
import posixpath

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core import textfmt, vmtext
from app.core.clipstore import ClipError, ClipNotFound
from app.deps import get_state, require_ready, verify_token
from app.models.inventory import OS
from app.transports.base import TransportError

router = APIRouter(prefix="/api/vmtext", tags=["vmtext"], dependencies=[Depends(verify_token)])


class TypeRequest(BaseModel):
    target: str
    text: str | None = None
    credential: str | None = None  # type this entry's password instead of `text`


class PushRequest(BaseModel):
    target: str
    board: str = "main"
    item_id: str | None = None  # default: latest item on the board
    remote_path: str | None = None  # default: the drop folder + item name
    eol: str = "auto"  # auto (target OS) | keep | lf | crlf
    sanitize: bool = False
    encoding: textfmt.Encoding = "utf8"


class PullRequest(BaseModel):
    target: str
    remote_path: str
    board: str = "main"


def _target(session, name: str):
    t = session.inventory.by_name(name)
    if t is None:
        raise HTTPException(status_code=404, detail=f"unknown target: {name}")
    return t


@router.post("/type")
async def type_into_vm(body: TypeRequest, session=Depends(require_ready)) -> dict:
    t = _target(session, body.target)
    max_chars = session.settings.clipboard.type_text_max_chars
    try:
        if body.credential:
            await vmtext.type_credential_into_vm(session.pool, t, entry=body.credential,
                                                 max_chars=max_chars)
            detail = {"source": "credential", "entry": body.credential}
        elif body.text:
            await vmtext.type_into_vm(session.pool, t, text=body.text, max_chars=max_chars)
            detail = {"source": "text", "chars": len(body.text)}
        else:
            raise HTTPException(status_code=400, detail="provide text or credential")
    except TransportError as exc:
        session.audit.record(action="type-into-vm", target=body.target, result="error",
                             detail={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.audit.record(action="type-into-vm", target=body.target, result="ok", detail=detail)
    return {"target": body.target, "typed": True}


@router.post("/push")
async def push(request: Request, body: PushRequest, session=Depends(require_ready)) -> dict:
    store = get_state(request).clipstore
    t = _target(session, body.target)
    try:
        item = store.get(body.board, body.item_id) if body.item_id else store.latest(body.board)
        if item.kind == "text":
            eol = textfmt.eol_for_os(t.os.value) if body.eol == "auto" else body.eol
            data = textfmt.deliver(store.read_text(body.board, item.id), eol=eol,  # type: ignore[arg-type]
                                   do_sanitize=body.sanitize, encoding=body.encoding)
        else:
            data = store.read_bytes(body.board, item.id)
    except ClipNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClipError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    files = session.settings.files
    name = item.name or (f"clip-{item.id}.txt" if item.kind == "text" else f"clip-{item.id}.bin")
    remote = body.remote_path or vmtext.default_drop_path(t, name, files.windows_drop_dir,
                                                          files.linux_drop_dir)
    try:
        transport = await vmtext.push_to_vm(session.pool, t, data=data, remote_path=remote)
        # Read back and compare checksums: a push isn't done until the bytes are proven there.
        back = await vmtext.pull_from_vm(session.pool, t, remote_path=remote)
    except TransportError as exc:
        session.audit.record(action="clip-push", target=body.target, result="error",
                             detail={"item": item.id, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sha = hashlib.sha256(data).hexdigest()
    verified = hashlib.sha256(back).hexdigest() == sha
    session.audit.record(action="clip-push", target=body.target, transport=transport,
                         result="ok" if verified else "mismatch",
                         detail={"item": item.id, "path": remote, "bytes": len(data)})
    if not verified:
        raise HTTPException(status_code=500, detail=f"checksum mismatch after writing {remote}")
    return {"target": body.target, "path": remote, "bytes": len(data), "sha256": sha,
            "transport": transport, "verified": True}


@router.post("/pull")
async def pull(request: Request, body: PullRequest, session=Depends(require_ready)) -> dict:
    store = get_state(request).clipstore
    t = _target(session, body.target)
    try:
        data = await vmtext.pull_from_vm(session.pool, t, remote_path=body.remote_path)
    except TransportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sep = "/" if t.os == OS.LINUX else "\\"
    name = posixpath.basename(body.remote_path.replace(sep, "/")) or "pulled"
    text = _as_text(data)
    if text is not None:  # show it inline on the board; bytes (incl. line endings) unchanged
        item = store.add_text(body.board, text, origin=t.name, name=name)
    else:
        item = store.add_file(body.board, name, io.BytesIO(data), origin=t.name)
    session.audit.record(action="clip-pull", target=body.target, result="ok",
                         detail={"path": body.remote_path, "item": item.id, "bytes": len(data)})
    return item.to_dict()


def _as_text(data: bytes) -> str | None:
    """Plain UTF-8 text without a BOM or NULs round-trips byte-exact as a text item."""
    if len(data) > 1 << 20 or b"\x00" in data or data.startswith(b"\xef\xbb\xbf"):
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
