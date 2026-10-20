# GP-0 Seed — privileged service account resident on RAC (2026-10-20)

Makes "Red extracts an admin hash from RAC" reliable and repeatable. Built by
`scripts/build_seed.py` (password generated at runtime, stored only in the credential store).

## What was created

- **DC (`DMZH2_DC` 10.1.20.17):** domain account `np\svc_backup`, **member of Domain Admins**.
  ```
  CREATED svc_backup
  MemberOf: CN=Domain Admins,CN=Users,DC=np,DC=local
  ```
- **RAC (`L4H1_RAC` 10.5.20.10):** scheduled task `LabBackupAgent`, trigger At-Startup, RunLevel
  Highest, running as `np\svc_backup` (a hidden long-sleep powershell). Keeps the account's NT hash
  resident in LSASS across reboots.
  ```
  Task state: Running
  Resident as: NP\svc_backup
  ```
- **Credential store:** entry `np.local/svc_backup` added (trainer-only; the drill secret).

## Why it is built this way

Pass-the-hash needs an admin hash *present in memory* on the box Red lands on. A one-off admin
logon is wiped by reboot; a **service/scheduled task running as the account keeps the hash resident**
continuously and is a realistic, common real-world weakness ("over-privileged service account").
Story for students: an IT "backup agent" runs on RAC under a Domain Admin account.

## Reset / teardown (between cohorts)

- RAC: `Unregister-ScheduledTask -TaskName LabBackupAgent -Confirm:$false`
- DC: `Remove-ADUser svc_backup` (or disable). Remove the `np.local/svc_backup` credential entry.
