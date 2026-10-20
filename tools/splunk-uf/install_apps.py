"""Install Splunkbase app packages from tools/splunk-uf/apps-incoming/ into DMZH1_SIEM etc\\apps.

usage: python -I -X utf8 tools/splunk-uf/install_apps.py <backend_dir> <pkg.tgz> [<pkg.tgz> ...] [--upgrade]

Per package: re-inspect it (same checks as splunkbase_fetch.py: one app folder, safe paths,
app.conf version) -> copy to D:\\SplunkStaging\\apps\\ (SMB, else the shell) + sha256 check on
the SIEM -> if the app is already installed: same version = skip; other version = only with
--upgrade (old folder moved to D:\\SplunkConfigBackup\\apps\\, its local\\ and
metadata\\local.meta carried over) -> tar.exe extract into etc\\apps -> read the version back.
Does NOT restart Splunk: run `deploy_ds.py backend --restart` afterwards.
"""
import asyncio
import hashlib
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

TARGET = "DMZH1_SIEM"
SPLUNK_APPS = r"C:\Program Files\Splunk\etc\apps"
STAGE = r"D:\SplunkStaging\apps"
BACKUP = r"D:\SplunkConfigBackup\apps"
UPGRADE = "--upgrade" in sys.argv
PKGS = [Path(a) for a in sys.argv[2:] if not a.startswith("--")]


def ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def inspect_pkg(path: Path) -> tuple[str, str]:
    import io
    import re
    import tarfile
    data = path.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        names = tf.getnames()
        if any(n.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", n) or ".." in Path(n).parts for n in names):
            raise SystemExit(f"{path.name}: unsafe member paths")
        tops = {Path(n).parts[0] for n in names if n not in (".", "./")}
        if len(tops) != 1:
            raise SystemExit(f"{path.name}: expected one app folder, got {sorted(tops)}")
        folder = tops.pop()
        text = tf.extractfile(f"{folder}/default/app.conf").read().decode("utf-8", "replace")
    m = re.search(r"(?m)^\s*version\s*=\s*(.+?)\s*$", text)
    return folder, (m.group(1) if m else "")


async def run(tr, script: str, what: str, timeout: int = 600) -> str:
    res = await tr.run(script, timeout=timeout)
    if res.exit_code not in (0, None):
        raise SystemExit(f"[{what}] failed:\n{res.stdout[-1500:]}\n{res.stderr[:1500]}")
    return res.stdout.strip()


async def main() -> None:
    if not PKGS:
        raise SystemExit(__doc__)
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    audit = AuditLog(settings.audit_abs)
    tr = await pool.shell(TARGET)  # identity-checked
    ft = await pool.file_transport(TARGET)
    print(f"== {TARGET}: shell via {tr.name}, files via {ft.name}")
    await run(tr, f"New-Item -ItemType Directory -Force -Path {ps(STAGE)}, {ps(BACKUP)} | Out-Null", "mkdir")
    for pkg in PKGS:
        folder, ver = inspect_pkg(pkg)
        sha = hashlib.sha256(pkg.read_bytes()).hexdigest()
        dest = f"{STAGE}\\{pkg.name}"
        print(f"### {folder} {ver} ({pkg.name})")
        try:
            await ft.put_file(str(pkg), dest)
        except Exception as exc:  # noqa: BLE001 - SMB errors are smbclient/OSError types
            print(f"   {ft.name} copy failed ({type(exc).__name__}); using the shell copy")
            await tr.put_file(str(pkg), dest)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = await run(tr, f"""
$ErrorActionPreference = 'Stop'
$pkg = {ps(dest)}; $apps = {ps(SPLUNK_APPS)}; $app = Join-Path $apps {ps(folder)}
$h = (Get-FileHash -LiteralPath $pkg -Algorithm SHA256).Hash.ToLower()
if ($h -ne '{sha}') {{ throw "sha256 mismatch on the SIEM: $h" }}
"staged + sha256 verified"
$have = ''
if (Test-Path "$app\\default\\app.conf") {{ $m = Select-String -Path "$app\\default\\app.conf" -Pattern '^\\s*version\\s*=\\s*(.+?)\\s*$' | Select-Object -First 1; if ($m) {{ $have = $m.Matches[0].Groups[1].Value }} }}
if ($have -eq '{ver}') {{ "already installed ($have) - skipped"; return }}
$carry = $null
if (Test-Path $app) {{
  if (-not {'$true' if UPGRADE else '$false'}) {{ throw "installed version '$have' differs from {ver}; re-run with --upgrade" }}
  $bk = Join-Path {ps(BACKUP)} ("{folder}-$have-{stamp}")
  Move-Item -LiteralPath $app -Destination $bk
  $carry = $bk; "old version $have moved to $bk"
}}
$o = cmd /c "tar.exe -xzf `"$pkg`" -C `"$apps`" 2>&1"
if ($LASTEXITCODE -ne 0) {{ throw "tar failed: $o" }}
if ($carry) {{
  if (Test-Path "$carry\\local") {{ Copy-Item "$carry\\local" "$app\\local" -Recurse -Force; "carried over local\\" }}
  if (Test-Path "$carry\\metadata\\local.meta") {{ Copy-Item "$carry\\metadata\\local.meta" "$app\\metadata\\local.meta" -Force; "carried over metadata\\local.meta" }}
}}
$m = Select-String -Path "$app\\default\\app.conf" -Pattern '^\\s*version\\s*=\\s*(.+?)\\s*$' | Select-Object -First 1
"installed: version $($m.Matches[0].Groups[1].Value), $((Get-ChildItem $app -Recurse -File).Count) files"
""", f"install {folder}")
        print("   " + out.replace("\n", "\n   "))
        audit.record(action="splunk.app-install", target=TARGET, transport=str(tr.name), result="ok",
                     detail={"app": folder, "version": ver, "sha256": sha})


asyncio.run(main())
