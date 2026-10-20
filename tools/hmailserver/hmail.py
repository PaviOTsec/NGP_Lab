"""hMailServer on L4H1_MailServer, step by step, through the identity-checked session pool.

usage: python -I -X utf8 tools/hmailserver/hmail.py <backend-dir> <step> [<target>]
  install    copy the installer (sha256-checked on the target) and install silently
  run <ps1>  run a script from this folder on <target> (default L4H1_MailServer); if the script
             contains __SECRETS__, a JSON of the mail credentials is copied over SMB first and the
             script is expected to delete it (passwords never travel inside script text, which
             PowerShell/Operational -> Splunk could record)

The installer is the single hMailServer-*-x64.exe in tools/hmailserver/installer/ (from the
official GitHub release; unsigned upstream, so its sha256 is pinned below).
"""
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
CREDS = BACKEND.parent / "config" / "credentials.example.yaml"
REMOTE_DIR = r"C:\ProgramData\LabConsole\hmail"
MAILSERVER = "L4H1_MailServer"
# GitHub release asset digest for hMailServer-5.7.1-B3116-x64.exe (built by the repo's Actions).
PINNED = {"hMailServer-5.7.1-B3116-x64.exe": "e86a7d4a6a8f44227b730b1e2f2173ae191a753d79b32d3633e55fa83f10ae21",
          "Thunderbird Setup 153.5.0esr.msi": "c5108331d0d8bf3313ef9e2359cbfd024fbb417bd17d6aba94429b8a9dcdf524"}


def ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


async def run(tr, script: str, what: str, timeout: int = 600) -> str:
    res = await tr.run(script, timeout=timeout)
    out = res.stdout + (f"\n[stderr] {res.stderr[:1500]}" if res.stderr else "")
    if res.exit_code not in (0, None):
        raise RuntimeError(f"{what} failed:\n{out[-3000:]}")
    return out


async def put(pool: SessionPool, tr, target: str, local: Path, dest: str) -> None:
    await run(tr, f"New-Item -ItemType Directory -Force -Path {ps(REMOTE_DIR)} | Out-Null", "mkdir")
    ft = await pool.file_transport(target)
    try:
        await ft.put_file(str(local), dest)
    except Exception as exc:  # noqa: BLE001 - SMB errors surface as smbclient/OSError types
        print(f"   {ft.name} copy failed ({type(exc).__name__}); using the shell copy")
        await tr.put_file(str(local), dest)


async def copy_pinned(pool: SessionPool, tr, target: str, local: Path) -> str:
    want = PINNED[local.name]
    if sha256(local) != want:
        raise SystemExit(f"{local.name}: local sha256 does not match the pinned digest")
    dest = f"{REMOTE_DIR}\\{local.name}"
    check = f"if (Test-Path -LiteralPath {ps(dest)}) {{ (Get-FileHash -LiteralPath {ps(dest)} -Algorithm SHA256).Hash.ToLower() }}"
    if (await run(tr, check, "hash")).strip() != want:
        await put(pool, tr, target, local, dest)
        if (await run(tr, check, "hash")).strip() != want:
            raise RuntimeError("sha256 mismatch after copy")
    print(f"   {local.name} on target, sha256 verified")
    return dest


def secrets_json(creds: CredentialStore) -> dict:
    accounts = {}
    for name in creds.names():
        if name.startswith("mail/"):
            c = creds.credential(name)
            accounts[c.username] = c.password
    return {"admin_password": creds.credential("hmailserver/Administrator").password, "accounts": accounts}


async def main() -> None:
    step = sys.argv[2] if len(sys.argv) > 2 else ""
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    creds = CredentialStore.load(CREDS)
    pool = SessionPool(settings=s, inventory=inv, creds=creds)
    audit = AuditLog(s.audit_abs)

    if step == "install":
        tr = await pool.shell(MAILSERVER)
        print(f"   session via {tr.name}")
        exe = [p for p in (HERE / "installer").glob("hMailServer-*-x64.exe")]
        if len(exe) != 1:
            raise SystemExit("need exactly one hMailServer-*-x64.exe in installer/")
        dest = await copy_pinned(pool, tr, MAILSERVER, exe[0])
        script = (HERE / "install_hmail.ps1").read_text(encoding="utf-8").replace("__EXE__", dest.replace("'", "''"))
        out = await run(tr, script, "install", timeout=900)
        print("   " + out.strip().replace("\n", "\n   "))
        audit.record(action="hmail.install", target=MAILSERVER, transport=str(tr.name),
                     result="ok" if "service: Running" in out else "error",
                     detail={"installer": exe[0].name, "sha256": PINNED[exe[0].name]})
    elif step == "run":
        script_path = HERE / sys.argv[3]
        target = sys.argv[4] if len(sys.argv) > 4 else MAILSERVER
        tr = await pool.shell(target)
        print(f"   session via {tr.name}")
        code = script_path.read_text(encoding="utf-8-sig")
        if "__MSI__" in code:
            msi = next((HERE / "installer").glob("Thunderbird Setup *.msi"))
            code = code.replace("__MSI__", (await copy_pinned(pool, tr, target, msi)).replace("'", "''"))
        if "__SECRETS__" in code:
            dest = f"{REMOTE_DIR}\\secrets.json"
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / "secrets.json"
                tmp.write_text(json.dumps(secrets_json(creds)), encoding="utf-8")
                await put(pool, tr, target, tmp, dest)
            code = code.replace("__SECRETS__", dest)
        try:
            out = await run(tr, code, script_path.name, timeout=900)
            ok = True
        except RuntimeError as exc:
            out, ok = str(exc), False
        print("   " + out.strip().replace("\n", "\n   "))
        audit.record(action=f"hmail.{script_path.stem}", target=target, transport=str(tr.name),
                     result="ok" if ok else "error", detail={"script": script_path.name})
    else:
        raise SystemExit(__doc__)


asyncio.run(main())
