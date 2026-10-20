"""One-off: join L4H1_RAC to np.local via the console pool (identity-checked WinRM as local admin).
The domain-join password is read from the credential store at runtime and injected into the remote
PS as a SecureString; it is never written to disk or printed. Usage:
  python -I join_rac_domain.py <backend> [--join] [--restart] [--verify]
Default (no flags) = pre-checks + DNS set + connectivity test ONLY (no join). Add --join to join,
--restart to reboot after a successful join, --verify to just read domain state."""
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

FLAGS = set(sys.argv[2:])
DC_DNS = "10.1.20.17"
DOMAIN = "np.local"
JOIN_CRED = "np.local/Administrator"
TARGET = "L4H1_RAC"


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


async def run(tr, script: str, timeout: int = 300) -> str:
    res = await tr.run(script, timeout=timeout)
    out = res.stdout or ""
    if res.stderr:
        out += "\n[stderr] " + res.stderr[:3000]
    return out


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    target = next(t for t in inv.all() if t.name == TARGET)
    dom = creds.credential(JOIN_CRED)
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)
    tr = await pool._open_shell(target)
    audit = AuditLog(settings.audit_abs)

    if "--verify" in FLAGS:
        print(await run(tr, r"""
$cs = Get-CimInstance Win32_ComputerSystem
"PartOfDomain : " + [string]$cs.PartOfDomain
"Domain       : " + [string]$cs.Domain
"DNS          : " + ((Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object ServerAddresses | ForEach-Object { $_.InterfaceAlias + '=' + ($_.ServerAddresses -join ',') }) -join ' | ')
try { "SecureChannel: " + [string](Test-ComputerSecureChannel) } catch { "SecureChannel: (n/a)" }
"""))
        return

    # Pre-checks + DNS + connectivity (always)
    pre = r"""
$ErrorActionPreference='SilentlyContinue'
$cs = Get-CimInstance Win32_ComputerSystem
"BEFORE PartOfDomain : " + [string]$cs.PartOfDomain + "  Domain: " + [string]$cs.Domain
$ix = (Get-NetIPAddress -IPAddress 10.5.20.10 -AddressFamily IPv4).InterfaceIndex
"Active ifIndex      : " + [string]$ix
Set-DnsClientServerAddress -InterfaceIndex $ix -ServerAddresses @('%DC%') | Out-Null
"DNS now             : " + ((Get-DnsClientServerAddress -InterfaceIndex $ix -AddressFamily IPv4).ServerAddresses -join ',')
"Resolve %DOMAIN%    : " + [string]((Resolve-DnsName %DOMAIN% -Type A -ErrorAction SilentlyContinue).IPAddress -join ',')
$t = Test-NetConnection -ComputerName %DC% -Port 389 -WarningAction SilentlyContinue
"LDAP 389 to DC      : " + [string]$t.TcpTestSucceeded
""".replace("%DC%", DC_DNS).replace("%DOMAIN%", DOMAIN)
    print("===== PRE-CHECK / DNS =====")
    print(await run(tr, pre))

    if "--join" not in FLAGS:
        print("\n(no --join flag: stopped after pre-checks; nothing was joined)")
        return

    # Join. Password injected as SecureString; never printed.
    join = r"""
$ErrorActionPreference='Stop'
$u = %USER%
$p = ConvertTo-SecureString %PW% -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential($u,$p)
try {
  Add-Computer -DomainName %DOMAIN% -Credential $cred -Force -PassThru | Out-Null
  "JOIN RESULT         : OK"
} catch {
  "JOIN RESULT         : FAILED - " + $_.Exception.Message
  return
}
$cs = Get-CimInstance Win32_ComputerSystem
"AFTER PartOfDomain  : " + [string]$cs.PartOfDomain + "  Domain: " + [string]$cs.Domain
"(reboot required to complete)"
""".replace("%USER%", ps_quote(dom.username)).replace("%PW%", ps_quote(dom.password or "")).replace("%DOMAIN%", DOMAIN)
    print("\n===== JOIN =====")
    out = await run(tr, join)
    print(out)
    audit.record(action="drill.rac-domain-join", target=TARGET, transport=str(tr.name),
                 result="ok" if "JOIN RESULT         : OK" in out else "failed")

    if "--restart" in FLAGS and "JOIN RESULT         : OK" in out:
        print("\n===== RESTART =====")
        try:
            await run(tr, "Restart-Computer -Force", timeout=30)
        except Exception as exc:  # the channel drops as it reboots - expected
            print("restart issued (channel dropped: %s)" % str(exc)[:120])
        print("RAC is rebooting; re-run with --verify in ~90s.")


asyncio.run(main())
