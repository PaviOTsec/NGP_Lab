"""File transfer routes. Upload lands on MC01's temp dir first, then goes to the target over
the fastest file transport (SMB for Windows, SFTP for Linux). Download reverses it.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.deps import require_ready, verify_token
from app.transports.base import TransportError

router = APIRouter(prefix="/api/files", tags=["files"], dependencies=[Depends(verify_token)])


@router.post("/upload")
async def upload(
    target: str = Form(...),
    remote_path: str = Form(...),
    file: UploadFile = Form(...),  # noqa: B008
    session=Depends(require_ready),
) -> dict:
    t = session.inventory.by_name(target)
    if t is None:
        raise HTTPException(status_code=404, detail=f"unknown target: {target}")

    # stage to MC01 temp, then push over the file transport
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        staged = tmp.name
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)
    try:
        transport = await session.pool.file_transport(target)
        written = await transport.put_file(staged, remote_path)
    except TransportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        try:
            os.unlink(staged)
        except OSError:
            pass

    session.audit.record(action="file-upload", target=target, transport=transport.name,
                         result="ok", detail={"remote_path": remote_path, "bytes": written})
    return {"target": target, "remote_path": remote_path, "bytes": written}


@router.get("/download")
async def download(target: str, remote_path: str, session=Depends(require_ready)):
    t = session.inventory.by_name(target)
    if t is None:
        raise HTTPException(status_code=404, detail=f"unknown target: {target}")

    fd, staged = tempfile.mkstemp()
    os.close(fd)
    try:
        transport = await session.pool.file_transport(target)
        await transport.get_file(remote_path, staged)
    except TransportError as exc:
        try:
            os.unlink(staged)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail=str(exc))

    session.audit.record(action="file-download", target=target, transport=transport.name,
                         result="ok", detail={"remote_path": remote_path})
    filename = os.path.basename(remote_path.replace("\\", "/")) or "download"
    return FileResponse(staged, filename=filename, background=_cleanup(staged))


def _cleanup(path: str):
    from starlette.background import BackgroundTask

    def _rm() -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    return BackgroundTask(_rm)
