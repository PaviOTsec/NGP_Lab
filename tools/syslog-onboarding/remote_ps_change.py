"""Run one STATE-CHANGING PowerShell snippet on an inventory target via the console's session pool
(identity-checked WinRM / PowerShell Direct) and audit it under the given action name.
The snippet must read its own result back and print it (a call without an error is not proof).
usage: python -I remote_ps_change.py <backend> <target> <ps-file> <audit-action>"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    target = next(t for t in inv.all() if t.name == sys.argv[2])
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    tr = await pool._open_shell(target)
    res = await tr.run(Path(sys.argv[3]).read_text(encoding="utf-8-sig"), timeout=300)
    AuditLog(settings.audit_abs).record(action=sys.argv[4], target=target.name, transport=str(tr.name),
                                        result="error" if res.stderr else "ok",
                                        detail={"script": Path(sys.argv[3]).name})
    print(res.stdout)
    if res.stderr:
        print("[stderr]", res.stderr[:2000])


asyncio.run(main())
