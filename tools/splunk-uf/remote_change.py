"""Run one CHANGE PowerShell script on inventory targets via the identity-checked session pool,
and record it in the audit log as a change (remote_ps.py is for read-only snippets).

usage: python -I -X utf8 tools/splunk-uf/remote_change.py <backend_dir> <audit-action> <ps-file> <target>...
"""
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

ACTION, SCRIPT, TARGETS = sys.argv[2], Path(sys.argv[3]), sys.argv[4:]


async def main() -> None:
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    pool = SessionPool(settings=s, inventory=inv, creds=CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml"))
    audit = AuditLog(s.audit_abs)
    code = SCRIPT.read_text(encoding="utf-8-sig")
    for name in TARGETS:
        print(f"### {name}")
        try:
            tr = await pool.shell(name)
            res = await tr.run(code, timeout=600)
            ok = res.exit_code in (0, None)
            print("   " + res.stdout.strip().replace("\n", "\n   "))
            if res.stderr:
                print("   [stderr] " + res.stderr.strip()[:800])
            audit.record(action=ACTION, target=name, transport=str(tr.name), result="ok" if ok else "error",
                         detail={"script": SCRIPT.name})
        except Exception as exc:  # noqa: BLE001 - keep going with the other hosts
            print(f"   FAILED: {exc}")
            audit.record(action=ACTION, target=name, result="error", detail={"script": SCRIPT.name, "error": str(exc)[:300]})


asyncio.run(main())
