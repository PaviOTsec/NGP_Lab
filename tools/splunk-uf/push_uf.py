"""Install the Splunk Universal Forwarder on lab Windows hosts and check they reach the SIEM.

usage: python -I -X utf8 tools/splunk-uf/push_uf.py <backend-dir> <target> [<target> ...]
           [--dry-run] [--reinstall] [--local-system]
       <target> = inventory name, or the word `default` for the standard set below.

The MSI is the single splunkforwarder-*.msi in tools/splunk-uf/installer/ (download it there
from splunk.com; its Authenticode signature must be valid and signed by Splunk).

Per target: identity-checked session (pool) -> skip if a forwarder is already installed
(unless --reinstall) -> copy the MSI to C:\\ProgramData\\LabConsole\\splunk\\ (SMB, else
chunked over the shell) and check sha256 on the target -> msiexec (install_uf.ps1) ->
wait for the deployment apps to arrive and the forwarder to connect to 10.1.20.15:9997.
--dry-run does the checks and stops before copying. --local-system installs the service
as LocalSystem instead of the least-privilege NT SERVICE\\SplunkForwarder account (fallback if
a host can't read its Security log).
"""
import asyncio
import hashlib
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
DS = "10.1.20.15:8089"
REMOTE_DIR = r"C:\ProgramData\LabConsole\splunk"
UF_HOME = r"C:\Program Files\SplunkUniversalForwarder"
# Windows hosts with a working login (2026-10-16). Not included: DMZH1_SIEM (runs Splunk
# Enterprise itself), DMZH2_EPO (off, no password), L3H1_Historian / L4BM_OfficePC (no
# password yet), appliances and power-only VMs (never touched, CLAUDE.md rule 5).
DEFAULT = ["DMZH1_LogServer", "DMZH1_MSSQL", "DMZH2_DC", "DMZH2_ADWSUS", "DMZH2_MaintServer",
           "L4H1_RAC", "L4H1_Spare", "L4H1_MailServer"]
NEVER = {"DMZH1_SIEM"}

flags = {a for a in sys.argv[2:] if a.startswith("--")}
names = [a for a in sys.argv[2:] if not a.startswith("--")]
names = [n for a in names for n in (DEFAULT if a == "default" else [a])]
DRY, REINSTALL, LOCALSYS = "--dry-run" in flags, "--reinstall" in flags, "--local-system" in flags


def ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def find_msi() -> Path | None:
    found = sorted((HERE / "installer").glob("splunkforwarder-*.msi"))
    if not found and DRY:
        print("== no MSI yet (dry run continues: sessions + pre-checks only)")
        return None
    if len(found) != 1:
        raise SystemExit(f"need exactly one splunkforwarder-*.msi in {HERE / 'installer'}, found {len(found)}")
    msi = found[0]
    sig = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"$s = Get-AuthenticodeSignature -LiteralPath {ps(str(msi))}; \"$($s.Status)|$($s.SignerCertificate.Subject)\""],
        capture_output=True, text=True).stdout.strip()
    status, _, subject = sig.partition("|")
    if status != "Valid" or "Splunk" not in subject:
        raise SystemExit(f"{msi.name}: Authenticode signature not valid/Splunk ({sig!r}) - re-download it")
    print(f"== MSI {msi.name}  signed by {subject.split(',')[0]}")
    return msi


async def run(tr, script: str, what: str, timeout: int = 300) -> str:
    res = await tr.run(script, timeout=timeout)
    if res.exit_code not in (0, None):
        raise RuntimeError(f"{what}: {res.stdout[-1500:]}\n{res.stderr[:1500]}")
    return res.stdout


async def copy_msi(pool: SessionPool, tr, name: str, msi: Path, sha: str) -> str:
    dest = f"{REMOTE_DIR}\\{msi.name}"
    have = (await run(tr, f"if (Test-Path -LiteralPath {ps(dest)}) {{ (Get-FileHash -LiteralPath {ps(dest)} -Algorithm SHA256).Hash.ToLower() }}",
                      "hash")).strip()
    if have == sha:
        print("   MSI already on target (sha256 matches)")
        return dest
    await run(tr, f"New-Item -ItemType Directory -Force -Path {ps(REMOTE_DIR)} | Out-Null", "mkdir")
    t0 = time.monotonic()
    ft = await pool.file_transport(name)
    try:
        await ft.put_file(str(msi), dest)
        how = ft.name
    except Exception as exc:  # noqa: BLE001 - SMB errors surface as smbclient/OSError types
        print(f"   {ft.name} copy failed ({type(exc).__name__}); falling back to the shell copy (slow)")
        await tr.put_file(str(msi), dest)
        how = tr.name
    have = (await run(tr, f"(Get-FileHash -LiteralPath {ps(dest)} -Algorithm SHA256).Hash.ToLower()", "hash")).strip()
    if have != sha:
        raise RuntimeError(f"sha256 mismatch after copy ({have} != {sha})")
    print(f"   copied via {how} in {time.monotonic() - t0:.0f}s, sha256 verified")
    return dest


VERIFY = f"""
$uf = {ps(UF_HOME)}; $log = "$uf\\var\\log\\splunk\\splunkd.log"
$want = @('lab_all_outputs', 'lab_windows_inputs')
$deadline = (Get-Date).AddSeconds(300)
do {{
  Start-Sleep 10
  $have = @($want | Where-Object {{ Test-Path "$uf\\etc\\apps\\$_" }})
  $txt = ''; try {{ $fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite'); $txt = (New-Object IO.StreamReader($fs)).ReadToEnd(); $fs.Close() }} catch {{}}
  $conn = $txt -match 'Connected to idx=10\\.1\\.20\\.15:9997'
}} until (($have.Count -eq $want.Count -and $conn) -or (Get-Date) -gt $deadline)
$s = Get-CimInstance Win32_Service -Filter "Name='SplunkForwarder'"
"service: $([string]$s.State) as $($s.StartName)"
"version: " + ((Get-Content "$uf\\etc\\splunk.version" -ErrorAction SilentlyContinue | Select-String '^VERSION') -join '')
"deployment apps: " + ((Get-ChildItem "$uf\\etc\\apps" -Directory | Where-Object {{ $_.Name -like 'lab_*' }} | ForEach-Object {{ $_.Name }}) -join ', ')
"connected to 10.1.20.15:9997: $conn"
"recent forwarder problems:"
$txt -split "`n" | Where-Object {{ $_ -match ' (ERROR|WARN) +(TcpOutputProc|TcpOutputFd|DC:|DeploymentClient|HttpPubSubConnection|ExecProcessor|WinEventLog)' }} |
  ForEach-Object {{ ($_ -replace '^\\S+ \\S+ \\S+ ', '').Trim() }} | Sort-Object -Unique | Select-Object -Last 12
"""


async def one(pool: SessionPool, audit: AuditLog, inv: Inventory, name: str, msi: Path | None,
              sha: str) -> str:
    target = next((t for t in inv.all() if t.name == name), None)
    if target is None or name in NEVER or target.os.value != "windows":
        return f"skipped: not an installable Windows target"
    tr = await pool.shell(name)  # identity-checked; refuses power-only / appliance targets
    print(f"   session via {tr.name}")
    existing = (await run(tr, "$s = Get-CimInstance Win32_Service -Filter \"Name='SplunkForwarder'\"; "
                          "if ($s) { [string]$s.State }", "precheck")).strip()
    if existing and not REINSTALL:
        print(f"   forwarder already installed ({existing}); checking it")
        if DRY:
            return f"dry run: already installed ({existing})"
    else:
        if DRY or msi is None:
            return "dry run: would copy + install"
        dest = await copy_msi(pool, tr, name, msi, sha)
        script = ((HERE / "install_uf.ps1").read_text(encoding="utf-8")
                  .replace("__MSI__", dest.replace("'", "''")).replace("__DS__", DS)
                  .replace("__LOCALSYSTEM__", "1" if LOCALSYS else "0"))
        print("   " + (await run(tr, script, "install", timeout=900)).strip().replace("\n", "\n   "))
        audit.record(action="splunk.uf-install", target=name, transport=str(tr.name), result="ok",
                     detail={"msi": msi.name, "sha256": sha, "deployment_server": DS})
    out = (await run(tr, VERIFY, "verify", timeout=420)).strip()
    print("   " + out.replace("\n", "\n   "))
    return "ok" if "connected to 10.1.20.15:9997: True" in out else "installed, NOT yet connected (see above)"


async def main() -> None:
    if not names:
        raise SystemExit(__doc__)
    msi = find_msi()
    sha = ""
    if msi:  # streamed: the MSI is ~390 MB and MC01 is often short of RAM
        h = hashlib.sha256()
        with msi.open("rb") as f:
            while chunk := f.read(4 * 1024 * 1024):
                h.update(chunk)
        sha = h.hexdigest()
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    audit = AuditLog(settings.audit_abs)
    summary = {}
    for name in names:
        print(f"### {name}")
        try:
            summary[name] = await one(pool, audit, inv, name, msi, sha)
        except Exception as exc:  # noqa: BLE001 - keep going with the other hosts
            summary[name] = f"FAILED: {exc}"
            audit.record(action="splunk.uf-install", target=name, result="error",
                         detail={"error": str(exc)[:300]})
    print("\n== summary")
    for name, result in summary.items():
        print(f"   {name:20} {result}")


asyncio.run(main())
