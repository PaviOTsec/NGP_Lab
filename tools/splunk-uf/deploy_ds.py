"""Push the deployment-server config in tools/splunk-uf/ds/ to DMZH1_SIEM and restart Splunk.

usage: python -I -X utf8 tools/splunk-uf/deploy_ds.py <backend-dir> [--dry-run] [--force] [--restart]

  ds/apps/...             -> $SPLUNK_HOME\\etc\\apps\\...
  ds/deployment-apps/...  -> $SPLUNK_HOME\\etc\\deployment-apps\\...
  ds/system/local/...     -> $SPLUNK_HOME\\etc\\system\\local\\...

Steps: identity-checked session (pool) -> backup etc\\system\\local + etc\\deployment-apps to
D:\\SplunkConfigBackup and a copy on MC01 (Backups\\<date>-splunk-ds) -> plan (new/same/differs)
-> stop if a file we don't own would change (unless --force) -> write byte-exact + sha256
read-back -> D:\\SplunkData ACL for NT SERVICE\\Splunkd -> firewall rules 9997/8089 ->
btool check -> restart Splunkd -> verify listeners, classes, index paths, new splunkd.log errors.
--dry-run stops after the plan (backup still taken). Idempotent: unchanged files are skipped,
and the restart is skipped when nothing changed and Splunkd is running (--restart forces it).
"""
import asyncio
import hashlib
import json
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

TARGET = "DMZH1_SIEM"
SPLUNK_HOME = r"C:\Program Files\Splunk"
DATA_DIR = r"D:\SplunkData"
BACKUP_DIR = r"D:\SplunkConfigBackup"
DS_ROOT = Path(__file__).resolve().parent / "ds"
# In-scope lab subnets only (CLAUDE.md rule 13: nothing from L2 192.168.20.0/24 and below).
LAB_SUBNETS = ["10.1.20.0/24", "10.4.20.0/24", "10.5.20.0/24", "192.168.30.0/24", "192.168.100.0/24"]
FW_RULES = [("LabConsole - Splunk receiving 9997", 9997), ("LabConsole - Splunk management 8089", 8089)]
# Files outside these prefixes are not ours: changing them needs --force.
# Also the vendor-app local\ files this tool created (2026-10-16). If you change CIM settings in
# Splunk Web, copy them back into ds\ first, or this tool will overwrite them.
OWNED = ("apps\\lab_", "deployment-apps\\lab_", "apps\\Splunk_SA_CIM\\local\\macros.conf",
         "apps\\Splunk_TA_microsoft_sysmon\\local\\inputs.conf", "apps\\DA-ESS-ContentUpdate\\local\\",
         "apps\\DA-ESS-ContentUpdate\\metadata\\local.meta")

DRY = "--dry-run" in sys.argv
FORCE = "--force" in sys.argv
RESTART = "--restart" in sys.argv  # restart even if no file changed


def ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def local_files() -> list[tuple[str, bytes]]:
    out = []
    for p in sorted(DS_ROOT.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(DS_ROOT)).replace("/", "\\")
            out.append((rel, p.read_bytes()))
    return out


def remote_path(rel: str) -> str:
    return SPLUNK_HOME + "\\etc\\" + rel


async def run(tr, script: str, what: str, timeout: int = 300) -> str:
    res = await tr.run(script, timeout=timeout)
    if res.exit_code not in (0, None):
        raise SystemExit(f"[{what}] failed:\n{res.stdout}\n{res.stderr[:2000]}")
    return res.stdout


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    target = next(t for t in inv.all() if t.name == TARGET)
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    audit = AuditLog(settings.audit_abs)
    tr = await pool._open_shell(target)  # identity-checked (NTLM challenge must say DMZH1SIEM)
    print(f"== session to {TARGET} via {tr.name}")

    # 1. pre-check + backup
    stamp = time.strftime("%Y%m%d-%H%M%S")
    zip_remote = f"{BACKUP_DIR}\\splunk-etc-{stamp}.zip"
    out = await run(tr, f"""
$ErrorActionPreference = 'Stop'
$sh = {ps(SPLUNK_HOME)}
if (-not (Test-Path "$sh\\bin\\splunk.exe")) {{ throw "Splunk not found at $sh" }}
New-Item -ItemType Directory -Force -Path {ps(BACKUP_DIR)} | Out-Null
$stage = Join-Path $env:TEMP 'lab-splunk-backup-{stamp}'
New-Item -ItemType Directory -Force -Path "$stage\\system-local", "$stage\\deployment-apps" | Out-Null
Copy-Item "$sh\\etc\\system\\local\\*" "$stage\\system-local" -Recurse -Force
Copy-Item "$sh\\etc\\deployment-apps\\*" "$stage\\deployment-apps" -Recurse -Force
Get-ChildItem "$sh\\etc\\apps" -Directory | ForEach-Object {{ $_.Name }} | Set-Content "$stage\\apps-list.txt" -Encoding ascii
Get-Content "$sh\\etc\\splunk.version" | Set-Content "$stage\\splunk.version" -Encoding ascii
Compress-Archive -Path "$stage\\*" -DestinationPath {ps(zip_remote)} -Force
Remove-Item $stage -Recurse -Force
(Get-FileHash {ps(zip_remote)} -Algorithm SHA256).Hash
""", "backup")
    zip_sha = out.strip().splitlines()[-1].lower()
    local_bk = BACKEND.parent / "Backups" / f"{time.strftime('%Y%m%d')}-splunk-ds"
    local_bk.mkdir(parents=True, exist_ok=True)
    data = await tr.read_bytes(zip_remote)
    if hashlib.sha256(data).hexdigest() != zip_sha:
        raise SystemExit("backup copy to MC01 failed the sha256 check")
    (local_bk / Path(zip_remote).name).write_bytes(data)
    print(f"== backup {zip_remote} ({len(data)} bytes) -> {local_bk / Path(zip_remote).name}  sha256 ok")

    # 2. plan
    files = local_files()
    paths = [remote_path(r) for r, _ in files]
    out = await run(tr, "$r = @{}; foreach ($p in @(" + ",".join(ps(p) for p in paths) + ")) { "
                    "$r[$p] = if (Test-Path -LiteralPath $p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } else { '' } }; "
                    "$r | ConvertTo-Json -Compress", "plan")
    remote = json.loads(out.strip().splitlines()[-1])
    plan, blocked = [], []
    for rel, body in files:
        have = remote.get(remote_path(rel), "")
        want = hashlib.sha256(body).hexdigest()
        state = "new" if not have else ("same" if have == want else "differs")
        plan.append((rel, body, want, state))
        if state == "differs" and not rel.startswith(OWNED):
            blocked.append(rel)
        print(f"   {state:8} etc\\{rel}")
    if blocked and not FORCE:
        raise SystemExit(f"STOP: would overwrite files not created by this tool: {blocked} "
                         "(backed up above; re-run with --force to replace them)")
    changes = [p for p in plan if p[3] != "same"]
    if DRY:
        print(f"== dry run: {len(changes)} file(s) would change; nothing written")
        return

    # 3. write + read-back
    for rel, body, want, state in changes:
        await tr.write_bytes(remote_path(rel), body)
    out = await run(tr, "$r = @{}; foreach ($p in @(" + ",".join(ps(remote_path(c[0])) for c in changes) + ")) { "
                    "$r[$p] = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() }; $r | ConvertTo-Json -Compress",
                    "verify") if changes else "{}"
    got = json.loads(out.strip().splitlines()[-1] or "{}")
    bad = [c[0] for c in changes if got.get(remote_path(c[0])) != c[2]]
    if bad:
        raise SystemExit(f"read-back mismatch: {bad}")
    print(f"== wrote {len(changes)} file(s), sha256 verified")

    # 4. data dir ACL + firewall (idempotent, read back)
    subnets = ",".join(ps(s) for s in LAB_SUBNETS)
    fw = "\n".join(f"""
$n = {ps(name)}
if (-not (Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue)) {{
  New-NetFirewallRule -DisplayName $n -Direction Inbound -Action Allow -Protocol TCP -LocalPort {port} -RemoteAddress @({subnets}) -Profile Any | Out-Null }}
$r = Get-NetFirewallRule -DisplayName $n; $pf = $r | Get-NetFirewallPortFilter; $af = $r | Get-NetFirewallAddressFilter
"fw: $n enabled=$([string]$r.Enabled) action=$([string]$r.Action) port=$($pf.LocalPort) remote=$($af.RemoteAddress -join ',')"
""" for name, port in FW_RULES)
    print(await run(tr, f"""
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path {ps(DATA_DIR)} | Out-Null
$o = & icacls.exe {ps(DATA_DIR)} /grant 'NT SERVICE\\Splunkd:(OI)(CI)M' 2>&1
if ($LASTEXITCODE -ne 0) {{ throw "icacls failed: $o" }}
$acl = (Get-Acl {ps(DATA_DIR)}).Access | Where-Object {{ $_.IdentityReference -match 'Splunkd' }}
"acl: $($acl.IdentityReference) $($acl.FileSystemRights) inherit=$($acl.InheritanceFlags)"
{fw}
""", "acl+firewall"))

    running = (await run(tr, "[string](Get-Service Splunkd).Status", "status")).strip() == "Running"
    if not changes and running and not RESTART:
        print("== nothing changed; Splunk not restarted")
        return

    # 5. btool check, restart, verify
    print(await run(tr, f"""
$sh = {ps(SPLUNK_HOME)}
$chk = cmd /c "`"$sh\\bin\\splunk.exe`" btool check 2>&1" | Out-String
"btool check:"; if ($chk.Trim()) {{ $chk.Trim() }} else {{ "  (no problems reported)" }}
""", "btool check"))
    out = await run(tr, f"""
$ErrorActionPreference = 'Stop'
$sh = {ps(SPLUNK_HOME)}
$log = "$sh\\var\\log\\splunk\\splunkd.log"
$off = (Get-Item $log).Length
# Use Splunk's own `splunk stop` / `splunk start`, never Stop/Restart-Service: splunkd's shutdown
# takes ~30 s here (the SCM's limit), and a cut-short stop force-kills the supervisor's sidecars
# (KV store / PostgreSQL / IPC broker) - on 2026-10-16 that left the KV store failing.
if ((Get-Service Splunkd).Status -ne 'Stopped') {{
  $o = cmd /c "`"$sh\\bin\\splunk.exe`" stop 2>&1"; "stop: " + (($o | Where-Object {{ $_ }}) -join ' | ')
  $d = (Get-Date).AddSeconds(240)
  while ((Get-Service Splunkd).Status -ne 'Stopped' -and (Get-Date) -lt $d) {{ Start-Sleep 3 }}
  if ((Get-Service Splunkd).Status -ne 'Stopped') {{ throw "Splunkd did not stop within 240 s" }}
}}
# Nothing from the old instance may survive (an orphaned postgres keeps its lock / port).
$d = (Get-Date).AddSeconds(90)
do {{ $left = @(Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -like "$sh\\*" }}); if ($left.Count) {{ Start-Sleep 5 }} }}
until ($left.Count -eq 0 -or (Get-Date) -gt $d)
if ($left.Count) {{ throw ("left running after stop (not killed - check first): " + (($left | ForEach-Object {{ "$($_.Name)#$($_.ProcessId)" }}) -join ' ')) }}
"stopped cleanly; no Splunk processes left"
$o = cmd /c "`"$sh\\bin\\splunk.exe`" start --no-prompt --answer-yes 2>&1"; "start: " + ((($o | Where-Object {{ $_ }}) | Select-Object -Last 3) -join ' | ')
$deadline = (Get-Date).AddSeconds(300)
do {{ Start-Sleep 5; $l = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in 8089, 9997 }} | ForEach-Object {{ $_.LocalPort }} | Sort-Object -Unique) }}
until ($l.Count -ge 2 -or (Get-Date) -gt $deadline)
$ErrorActionPreference = 'Continue'
"service: $([string](Get-Service Splunkd).Status)"
"listening: $($l -join ',')"
"serverclasses: " + ((& "$sh\\bin\\splunk.exe" btool serverclass list 2>$null | Select-String '^\\[serverClass:[^:\\]]+\\]' | ForEach-Object {{ $_.Line }}) -join ' ')
"wineventlog homePath: " + ((& "$sh\\bin\\splunk.exe" btool indexes list wineventlog 2>$null | Select-String '^homePath') -join '')
"index dir created: $(Test-Path '{DATA_DIR}\\wineventlog\\db')"
"deployment-apps: " + ((Get-ChildItem "$sh\\etc\\deployment-apps" -Directory | ForEach-Object {{ $_.Name }}) -join ', ')
# KV store (Splunk 10: kvstore-pdl sidecar on PostgreSQL): ready = 3 healthy checks in a row.
$kv = "$sh\\var\\log\\splunk\\sup-pkg-kvstore-pdl.log"; $ok = 0; $d = (Get-Date).AddSeconds(420)
$kvoff = if (Test-Path $kv) {{ (Get-Item $kv).Length }} else {{ 0 }}
do {{
  Start-Sleep 10
  $fs = [IO.File]::Open($kv, 'Open', 'Read', 'ReadWrite'); try {{ if ($fs.Length -lt $kvoff) {{ $kvoff = 0 }}; $null = $fs.Seek($kvoff, 'Begin'); $new = (New-Object IO.StreamReader($fs)).ReadToEnd(); $kvoff = $fs.Length }} finally {{ $fs.Close() }}
  if ($new -match 'failed|error') {{ $ok = 0 }} elseif ($new -match 'healthy') {{ $ok++ }}
}} until ($ok -ge 3 -or (Get-Date) -gt $d)
"kvstore: " + $(if ($ok -ge 3) {{ "healthy (3 consecutive checks)" }} else {{ "NOT healthy after 7 min - see var\\log\\splunk\\sup-pkg-kvstore-pdl.log" }})
Start-Sleep 5
$fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite'); try {{
  if ($fs.Length -lt $off) {{ $off = 0 }}; $null = $fs.Seek($off, 'Begin')
  $txt = (New-Object IO.StreamReader($fs)).ReadToEnd() }} finally {{ $fs.Close() }}
"new splunkd.log ERROR/WARN lines (deduplicated, max 40):"
$txt -split "`n" | Where-Object {{ $_ -match ' (ERROR|WARN) ' }} | ForEach-Object {{ ($_ -replace '^\\S+ \\S+ \\S+ ', '').Trim() }} | Sort-Object -Unique | Select-Object -First 40
""", "restart+verify", timeout=1200)
    print(out)
    audit.record(action="splunk.ds-deploy", target=TARGET, transport=str(tr.name), result="ok",
                 detail={"changed": [c[0] for c in changes], "backup": zip_remote})


asyncio.run(main())
