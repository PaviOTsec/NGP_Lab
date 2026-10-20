"""Install Microsoft Sysmon with the sysmon-modular "Balanced" config on lab Windows hosts.

usage: python -I -X utf8 tools/sysmon/push_sysmon.py <backend_dir> <target>... [--dry-run] [--update-config]
       <target> = inventory name, or `default` (the 8 forwarder hosts + DMZH1_SIEM)

Inputs (downloaded 2026-10-16, see README): incoming/Sysmon/Sysmon64.exe (15.22, signed by
Microsoft) and incoming/sysmonconfig-15.21.xml (release configs-a45dedb13a43, sha256 pinned below).
Per host: identity-checked session -> already installed? report (or `-c` with --update-config)
-> copy both files to C:\\ProgramData\\LabConsole\\sysmon\\ (SMB, else the shell) -> sha256 +
Authenticode (Microsoft) checked ON the host -> `Sysmon64.exe -accepteula -i <config>` ->
verify service Sysmon64 + driver SysmonDrv running, the event log has events, config hash.
Never on appliances / power-only VMs (the pool refuses a shell for them).
"""
import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
EXE = HERE / "incoming" / "Sysmon" / "Sysmon64.exe"
# Lab config = release Balanced 15.21 + full ProcessCreate (built by build_config.py, which checks
# the release file's sha256); its own sha256 is in the .sha256 sidecar written by the build.
CFG = HERE / "sysmonconfig-lab.xml"
CFG_SHA = (HERE / "sysmonconfig-lab.xml.sha256").read_text(encoding="ascii").strip()
REMOTE = r"C:\ProgramData\LabConsole\sysmon"
DEFAULT = ["DMZH1_LogServer", "DMZH1_MSSQL", "DMZH2_DC", "DMZH2_ADWSUS", "DMZH2_MaintServer",
           "L4H1_RAC", "L4H1_Spare", "L4H1_MailServer", "DMZH1_SIEM"]

flags = {a for a in sys.argv[2:] if a.startswith("--")}
names = [n for a in sys.argv[2:] if not a.startswith("--") for n in (DEFAULT if a == "default" else [a])]
DRY, UPDATE = "--dry-run" in flags, "--update-config" in flags


def ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def check_local() -> tuple[str, str]:
    cfg = sha256(CFG)
    if cfg != CFG_SHA:
        raise SystemExit(f"{CFG.name}: sha256 {cfg} != {CFG_SHA} from the build - re-run build_config.py")
    sig = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                          f"$s = Get-AuthenticodeSignature -LiteralPath {ps(str(EXE))}; \"$($s.Status)|$($s.SignerCertificate.Subject)\""],
                         capture_output=True, text=True).stdout.strip()
    if not sig.startswith("Valid|CN=Microsoft"):
        raise SystemExit(f"{EXE.name}: signature not valid/Microsoft ({sig!r})")
    print(f"== {EXE.name} signed by Microsoft; config {CFG.name} sha256 matches the build")
    return sha256(EXE), cfg


async def run(tr, script: str, what: str, timeout: int = 300) -> str:
    res = await tr.run(script, timeout=timeout)
    if res.exit_code not in (0, None):
        raise RuntimeError(f"{what}: {res.stdout[-1500:]}\n{res.stderr[:1500]}")
    return res.stdout.strip()


STATE = """
$s = Get-CimInstance Win32_Service -Filter "Name='Sysmon64' OR Name='Sysmon'"
if ($s) { "installed: $($s.Name) $([string]$s.State) $($s.PathName)" } else { "not installed" }
"""

VERIFY = f"""
$exe = {ps(REMOTE + chr(92) + 'Sysmon64.exe')}
$s = Get-CimInstance Win32_Service -Filter "Name='Sysmon64'"
# SysmonDrv is a file-system minifilter: it isn't in Win32_SystemDriver, so ask the SCM.
$d = if ((cmd /c "sc.exe query SysmonDrv 2>&1") -match 'STATE\\s+:\\s+4\\s+RUNNING') {{ 'Running' }} else {{ 'not running' }}
"service Sysmon64: $([string]$s.State) start=$([string]$s.StartMode) | driver SysmonDrv: $d"
$e = Get-WinEvent -LogName 'Microsoft-Windows-Sysmon/Operational' -MaxEvents 1 -ErrorAction SilentlyContinue
"newest Sysmon event: $(if ($e) {{ $e.TimeCreated.ToString('s') + ' id ' + $e.Id }} else {{ 'none' }})"
# Sysmon -c prints UTF-16; the loaded config's hash is in the driver's registry parameters.
"loaded config: " + (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\SysmonDrv\\Parameters' -ErrorAction SilentlyContinue).ConfigHash
"""


async def one(pool, audit, inv, name, exe_sha, cfg_sha) -> str:
    t = next((x for x in inv.all() if x.name == name), None)
    if t is None or t.os.value != "windows":
        return "skipped: not a Windows target"
    tr = await pool.shell(name)  # identity-checked; refuses appliances / power-only
    state = await run(tr, STATE, "state")
    print(f"   session via {tr.name}; {state}")
    exe_r, cfg_r = f"{REMOTE}\\Sysmon64.exe", f"{REMOTE}\\{CFG.name}"
    if state.startswith("installed") and not UPDATE:
        print("   " + (await run(tr, VERIFY, "verify")).replace("\n", "\n   "))
        return "already installed (use --update-config to load this config)"
    if DRY:
        return "dry run: would " + ("update the config" if state.startswith("installed") else "copy + install")
    await run(tr, f"New-Item -ItemType Directory -Force -Path {ps(REMOTE)} | Out-Null", "mkdir")
    ft = await pool.file_transport(name)
    for src, dst in ((EXE, exe_r), (CFG, cfg_r)):
        try:
            await ft.put_file(str(src), dst)
        except Exception as exc:  # noqa: BLE001 - SMB errors are smbclient/OSError types
            print(f"   {ft.name} copy failed ({type(exc).__name__}); using the shell copy")
            await tr.put_file(str(src), dst)
    out = await run(tr, f"""
$ErrorActionPreference = 'Stop'
$exe = {ps(exe_r)}; $cfg = {ps(cfg_r)}
if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() -ne '{exe_sha}') {{ throw 'Sysmon64.exe sha256 mismatch on the host' }}
if ((Get-FileHash $cfg -Algorithm SHA256).Hash.ToLower() -ne '{cfg_sha}') {{ throw 'config sha256 mismatch on the host' }}
$sig = Get-AuthenticodeSignature $exe
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch '^CN=Microsoft') {{ throw "signature on the host: $($sig.Status)" }}
"files verified on the host (sha256 + Microsoft signature)"
$args1 = if ({'$true' if UPDATE else '$false'} -and (Get-CimInstance Win32_Service -Filter "Name='Sysmon64'")) {{ "-c `"$cfg`"" }} else {{ "-accepteula -i `"$cfg`"" }}
$o = cmd /c "`"$exe`" $args1 2>&1"
"sysmon $args1 -> exit $LASTEXITCODE"
($o | Where-Object {{ $_ -match '(?i)error|fail|install|started|configuration|updated' }} | Select-Object -Last 6) -join "`n"
if ($LASTEXITCODE -ne 0) {{ throw "Sysmon64.exe exited with $LASTEXITCODE" }}
""", "install", timeout=600)
    print("   " + out.replace("\n", "\n   "))
    await asyncio.sleep(5)
    ver = await run(tr, VERIFY, "verify")
    print("   " + ver.replace("\n", "\n   "))
    ok = "service Sysmon64: Running" in ver and "driver SysmonDrv: Running" in ver
    audit.record(action="sysmon.install" if not UPDATE else "sysmon.update-config", target=name,
                 transport=str(tr.name), result="ok" if ok else "check", detail={"config_sha256": cfg_sha})
    return "ok" if ok else "installed, but service/driver not confirmed running (see above)"


async def main() -> None:
    if not names:
        raise SystemExit(__doc__)
    exe_sha, cfg_sha = check_local()
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    pool = SessionPool(settings=s, inventory=inv, creds=CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml"))
    audit = AuditLog(s.audit_abs)
    summary = {}
    for n in names:
        print(f"### {n}")
        try:
            summary[n] = await one(pool, audit, inv, n, exe_sha, cfg_sha)
        except Exception as exc:  # noqa: BLE001 - keep going with the other hosts
            summary[n] = f"FAILED: {exc}"
            audit.record(action="sysmon.install", target=n, result="error", detail={"error": str(exc)[:300]})
    print("\n== summary")
    for n, r in summary.items():
        print(f"   {n:20} {r}")


asyncio.run(main())
