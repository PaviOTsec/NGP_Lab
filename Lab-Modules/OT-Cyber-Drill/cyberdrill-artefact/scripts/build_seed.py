"""Build the drill seed: create np\\svc_backup (Domain Admin) on the DC, run it as a resident
scheduled task on RAC so its NT hash stays in LSASS across reboots, and store its password in the
credentials file (np.local/svc_backup). The generated password is never printed. Idempotent.
usage: python -I build_seed.py <backend>"""
import asyncio, secrets, string, sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

CREDS_PATH = BACKEND.parent / "config" / "credentials.example.yaml"


def ps_q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def gen_pw() -> str:
    # safe charset: no quotes/backticks/backslash/space; strong length
    alpha = string.ascii_letters + string.digits
    sym = "!@#%^*_-+=.?"
    pw = "".join(secrets.choice(alpha) for _ in range(20)) + secrets.choice(sym) + secrets.choice(string.ascii_uppercase) + secrets.choice(string.digits)
    return pw


async def run(tr, script, timeout=300):
    r = await tr.run(script, timeout=timeout)
    return (r.stdout or "") + (("\n[stderr] " + r.stderr[:2000]) if r.stderr else "")


async def main() -> None:
    settings = Settings.load()
    inv = Inventory.load(settings.inventory_path)
    creds = CredentialStore.load(CREDS_PATH)
    audit = AuditLog(settings.audit_abs)
    pool = SessionPool(settings=settings, inventory=inv, creds=creds)

    # reuse existing password if the entry already exists, else generate + persist
    try:
        pw = creds.credential("np.local/svc_backup").password
        made = False
    except Exception:
        pw = gen_pw()
        made = True

    # ---- DC: create account + add to Domain Admins ----
    dc = next(t for t in inv.all() if t.name == "DMZH2_DC")
    tr_dc = await pool._open_shell(dc)
    dc_ps = r"""
$ErrorActionPreference='Stop'
Import-Module ActiveDirectory
$pw = ConvertTo-SecureString %PW% -AsPlainText -Force
$u = Get-ADUser -Filter "SamAccountName -eq 'svc_backup'" -ErrorAction SilentlyContinue
if ($null -eq $u) {
  New-ADUser -Name 'svc_backup' -SamAccountName 'svc_backup' -DisplayName 'Lab Backup Agent' `
    -Description 'Backup agent service account' -AccountPassword $pw -Enabled $true -PasswordNeverExpires $true
  'CREATED svc_backup'
} else {
  Set-ADAccountPassword -Identity svc_backup -Reset -NewPassword $pw
  Enable-ADAccount -Identity svc_backup
  'EXISTS svc_backup (password reset)'
}
if (-not (Get-ADGroupMember 'Domain Admins' | Where-Object SamAccountName -eq 'svc_backup')) {
  Add-ADGroupMember -Identity 'Domain Admins' -Members svc_backup
}
'MemberOf: ' + ((Get-ADUser svc_backup -Properties MemberOf).MemberOf -join '; ')
""".replace("%PW%", ps_q(pw))
    print("===== DC: create svc_backup =====")
    print(await run(tr_dc, dc_ps))
    audit.record(action="drill.seed-create-dauser", target="DMZH2_DC", transport=str(tr_dc.name), result="ok")

    # ---- RAC: resident scheduled task running as svc_backup ----
    rac = next(t for t in inv.all() if t.name == "L4H1_RAC")
    tr_rac = await pool._open_shell(rac)
    rac_ps = r"""
$ErrorActionPreference='Stop'
$u='np\svc_backup'; $p=%PW%
$act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -Command "while($true){Start-Sleep -Seconds 3600}"'
$trg = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'LabBackupAgent' -Action $act -Trigger $trg -User $u -Password $p -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName 'LabBackupAgent'
Start-Sleep -Seconds 4
'Task state: ' + (Get-ScheduledTask -TaskName 'LabBackupAgent').State
$procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'"
$owners = foreach($pr in $procs){ $o=Invoke-CimMethod -InputObject $pr -MethodName GetOwner; if($o.User){ "$($o.Domain)\$($o.User)" } }
'Resident as: ' + (($owners | Sort-Object -Unique) -join ', ')
""".replace("%PW%", ps_q(pw))
    print("\n===== RAC: resident svc_backup task =====")
    print(await run(tr_rac, rac_ps))
    audit.record(action="drill.seed-resident-task", target="L4H1_RAC", transport=str(tr_rac.name), result="ok")

    # ---- persist the password into the credentials file (designated secret store) ----
    if made:
        text = CREDS_PATH.read_text(encoding="utf-8-sig")
        if "np.local/svc_backup" not in text:
            if not text.endswith("\n"):
                text += "\n"
            text += "  np.local/svc_backup:\n    username: NP\\svc_backup\n    password: " + '"' + pw + '"' + "\n"
            CREDS_PATH.write_text(text, encoding="utf-8")
            print("\n[creds] added entry np.local/svc_backup")
        # verify it reloads
        CredentialStore.load(CREDS_PATH).credential("np.local/svc_backup")
        print("[creds] reload OK")
    else:
        print("\n[creds] np.local/svc_backup already present (reused)")


asyncio.run(main())
