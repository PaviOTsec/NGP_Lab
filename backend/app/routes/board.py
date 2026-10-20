"""Shared clipboard board routes (the cl1p.net-style page the VMs open).

Mounted on BOTH servers:
  * the clipboard server (0.0.0.0:8766 by default) — no token, reachable from every VM;
  * the console (with the launch token) — so the console UI and agents see the same board.

Endpoints are deliberately curl/Invoke-WebRequest friendly so headless VMs can use them:

  GET    /r/{board}                    latest item, raw      (?eol=lf|crlf&sanitize=1&encoding=…)
  GET    /r/{board}/{id}               one item, raw
  POST   /api/clip/{board}/text        raw request body = text   (exact bytes kept)
  POST   /api/clip/{board}/upload      raw request body = file   (?name=file.ext)
  POST   /api/clip/{board}/files       multipart, one or more files (the page uses this)
  GET    /api/clip/{board}             item list (+ inline text for small text items)
  GET    /api/clip/{board}/version     cheap change counter for polling
  DELETE /api/clip/{board}/{id}        remove one item;  DELETE /api/clip/{board} clears it
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.core import textfmt
from app.core.audit import AuditLog
from app.core.clipstore import DEFAULT_BOARD, ClipError, ClipNotFound, ClipStore

PAGE = Path(__file__).resolve().parent.parent / "clip_page" / "index.html"

# Module level so FastAPI can resolve them as query-parameter types.
Eol = Literal["keep", "lf", "crlf"]
Enc = Literal["utf8", "utf8bom", "utf16le"]


def decode_body(data: bytes) -> str:
    """Decode posted text without guessing wrong on Windows clients.

    BOM wins; then strict UTF-8; then cp1252 (what Windows PowerShell 5.1 sends when no
    charset is given).
    """
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def make_router(store: ClipStore, audit: AuditLog, *, inline_text_bytes: int,
                serve_page: bool, dependencies: list | None = None) -> APIRouter:
    router = APIRouter(tags=["clipboard-board"], dependencies=dependencies or [])

    def _guard(fn):
        try:
            return fn()
        except ClipNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ClipError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _origin(request: Request) -> str:
        return request.client.host if request.client else ""

    # --- page ---

    if serve_page:
        @router.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(f"/b/{DEFAULT_BOARD}")

        @router.get("/b/{board}", include_in_schema=False)
        def page(board: str) -> HTMLResponse:
            _guard(lambda: store.version(board))
            return HTMLResponse(PAGE.read_text(encoding="utf-8"),
                                headers={"Cache-Control": "no-store"})

    # --- listing ---

    @router.get("/api/clip/{board}")
    def list_items(board: str) -> dict:
        items = _guard(lambda: store.list(board))
        out = []
        for it in items:
            d = it.to_dict()
            if it.kind == "text" and it.size <= inline_text_bytes:
                d["text"] = store.read_text(board, it.id)
            out.append(d)
        return {"board": board, "version": store.version(board), "items": out}

    @router.get("/api/clip/{board}/version")
    def version(board: str) -> dict:
        return {"version": _guard(lambda: store.version(board))}

    @router.get("/api/clip")
    def boards() -> dict:
        return {"boards": store.boards()}

    # --- adding ---

    @router.post("/api/clip/{board}/text")
    async def add_text(board: str, request: Request, name: str = "") -> dict:
        text = decode_body(await request.body())
        if not text:
            raise HTTPException(status_code=400, detail="empty text")
        item = _guard(lambda: store.add_text(board, text, origin=_origin(request), name=name))
        audit.record(action="clip-add", target=board, result="ok",
                     detail={"kind": "text", "id": item.id, "bytes": item.size,
                             "origin": item.origin})
        return item.to_dict()

    @router.post("/api/clip/{board}/upload")
    async def upload_raw(board: str, request: Request, name: str = "file") -> dict:
        # Spool the body (bounded memory), then hash/store it off the event loop.
        spool = tempfile.SpooledTemporaryFile(max_size=8 << 20)
        try:
            async for chunk in request.stream():
                spool.write(chunk)
            spool.seek(0)
            item = await asyncio.to_thread(
                _guard, lambda: store.add_file(board, name, spool, origin=_origin(request))
            )
        finally:
            spool.close()
        audit.record(action="clip-add", target=board, result="ok",
                     detail={"kind": "file", "id": item.id, "name": item.name,
                             "bytes": item.size, "origin": item.origin})
        return item.to_dict()

    @router.post("/api/clip/{board}/files")
    async def add_files(board: str, request: Request, files: list[UploadFile]) -> dict:
        added = []
        for f in files:
            item = await asyncio.to_thread(
                _guard,
                lambda f=f: store.add_file(board, f.filename or "file", f.file,
                                           origin=_origin(request)),
            )
            audit.record(action="clip-add", target=board, result="ok",
                         detail={"kind": "file", "id": item.id, "name": item.name,
                                 "bytes": item.size, "origin": item.origin})
            added.append(item.to_dict())
        return {"items": added}

    # --- raw delivery ---

    def _raw(board: str, item_id: str | None, eol: textfmt.Eol, sanitize: bool,
             encoding: textfmt.Encoding, download: bool, filename: str) -> Response:
        item = _guard(lambda: store.get(board, item_id) if item_id else store.latest(board))
        if item.kind == "file":
            # Files are delivered byte-exact, always.
            return FileResponse(store.blob_path(board, item.id), filename=item.name,
                                media_type="application/octet-stream",
                                content_disposition_type="attachment" if download else "inline")
        text = store.read_text(board, item.id)
        body = textfmt.deliver(text, eol=eol, do_sanitize=sanitize, encoding=encoding)
        charset = "utf-16" if encoding == "utf16le" else "utf-8"
        headers = {"X-Clip-Id": item.id, "X-Clip-Sha256": item.sha256, "Cache-Control": "no-store"}
        if download:
            fname = filename or item.name or f"clip-{item.id}.txt"
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(fname)}"
        return Response(body, media_type=f"text/plain; charset={charset}", headers=headers)

    @router.get("/r/{board}")
    def raw_latest(board: str, eol: Eol = "keep", sanitize: bool = False, encoding: Enc = "utf8",
                   download: bool = False, filename: str = "") -> Response:
        return _raw(board, None, eol, sanitize, encoding, download, filename)

    @router.get("/r/{board}/{item_id}")
    def raw_item(board: str, item_id: str, eol: Eol = "keep", sanitize: bool = False,
                 encoding: Enc = "utf8", download: bool = False, filename: str = "") -> Response:
        return _raw(board, item_id, eol, sanitize, encoding, download, filename)

    # --- removing ---

    @router.delete("/api/clip/{board}/{item_id}")
    def delete_item(board: str, item_id: str) -> dict:
        _guard(lambda: store.delete(board, item_id))
        return {"deleted": item_id}

    @router.delete("/api/clip/{board}")
    def clear_board(board: str) -> dict:
        _guard(lambda: store.clear(board))
        audit.record(action="clip-clear", target=board, result="ok")
        return {"cleared": board}

    return router
