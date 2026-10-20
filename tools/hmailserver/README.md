# Lab mail: hMailServer on L4H1_MailServer + Thunderbird on L4H1_RAC

Set up 2026-10-20 (operator request). Everything here was done remotely through the
identity-checked session pool; no GUI steps.

## What is where

| Item | Value |
|---|---|
| Server | L4H1_MailServer, 10.4.20.21 (workgroup, Server 2022, clock UTC) |
| Software | hMailServer **5.7.1-B3116 x64** (official GitHub release, built by the repo's Actions; unsigned upstream, sha256 `e86a7d4a…10ae21` pinned in `hmail.py`). 5.6.8 was rejected: its tools need .NET 2.0/3.5, removed on this VM. 5.7 needs .NET 4.5+ (VM has 4.8). |
| Data | `C:\ProgramData\hMailServer\` (ini, `Data\`, `Logs\`, built-in SQL CE database). Service `hMailServer` runs as `NT SERVICE\hMailServer`. |
| Domain | `mail.np.local` (server HostName + DefaultDomain, so `student1` also works as a login) |
| Accounts | admin, student1-8, trainee, remoteIT `@mail.np.local`, 1 GB each, no admin rights. Passwords: credentials file `mail/<account>` (pattern `<Name>@Mail26`). hMailServer Administrator (GUI/COM): `hmailserver/Administrator` (random). |
| Ports | SMTP 25 (inbound, no auth), SMTP 587 (auth), POP3 110, IMAP 143. No TLS (lab, plaintext on purpose; visible on SPAN). |
| IP ranges | `Lab networks 10.0.0.0/8` and `Lab networks 192.168.0.0/16`: connect + deliver to local mailboxes, auth required for local senders, **no relay**. `Outside lab (refused)` (was the default "Internet" range): no connections. `My computer` (127.0.0.1): default. |
| Auto-ban | default: 3 failed logons in 30 min bans the IP for 60 min (watch this during password-spray drills) |
| Windows Firewall | rule `LabConsole-hMailServer-Lab`: TCP 25/110/143/587 from 10.0.0.0/8, 192.168.0.0/16 |
| DNS (DMZH2_DC) | `mail.np.local` A 10.4.20.21 and MX 10 `mail.np.local.` in zone np.local |
| Client | L4H1_RAC: Thunderbird **153.5.0esr** (Mozilla-signed, sha256 matches Mozilla SHA256SUMS). `C:\Program Files\Mozilla Thunderbird\mozilla.cfg` (+ `defaults\pref\autoconfig.js`) presets `remoteIT@mail.np.local` (IMAP 143 / SMTP 587, normal password) for **every** Windows user via `defaultPref`; the password is typed on first use. `isp\mail.np.local.xml` makes "Add account" auto-fill server settings from email + password. `distribution\policies.json`: no updates, no telemetry. |
| Splunk | index `mail` (DMZH1_SIEM, D:\SplunkData\mail, 5 GB / 180 d); forwarder app `lab_hmailserver_inputs` (serverclass `lab_mailserver`, whitelist L4H1MAILSERVER); parsing app `lab_mail`. Sourcetypes: `hmailserver` (protocol log), `hmailserver:awstats` (one line per delivery attempt incl. refused), `hmailserver:error`. |

## MC01 (operator) client

Thunderbird 153.5.0esr installed locally (same verified MSI) for the Windows user Administrator,
profile `%APPDATA%\Thunderbird\Profiles\r2ie10q4.remoteIT` with **remoteIT@mail.np.local** preset
(`mc01_thunderbird_profile.ps1`). MC01's DNS doesn't resolve `mail.np.local`, so the server is the IP
**10.4.20.21** (IMAP 143 / SMTP 587). Thunderbird 153 ignores a fresh `Default=1` profile and makes its
own locked `default-esr` one on first launch: `profiles.ini` `[Install…]` and `installs.ini` were
pointed at the remoteIT profile and the empty `default-esr` deleted. Password typed once at the prompt.

## Passwords and logs

- No password ever travels in script text or on a command line (PowerShell/Operational and
  Sysmon go to Splunk). `hmail.py run` copies a `secrets.json` over SMB; the script deletes it.
- The installer's `/ADMINPASSWORD=` was deliberately not used; the admin password is set via
  COM `Settings.SetAdministratorPassword` (stored hashed in `hMailServer.ini`).
- `Logging.MaskPasswordsInLog` is a **no-op in 5.7** (reads back False). 5.7 masks SMTP AUTH,
  IMAP LOGIN and POP3 PASS unconditionally; confirmed on the live log (`LOGIN user ***`, `PASS ***`).
  SMTP AUTH LOGIN usernames are logged base64-encoded.

## Scripts (run from `backend\`)

```
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . install
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run configure_hmail.ps1      # idempotent; re-syncs passwords from the credentials file
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run firewall_hmail.ps1
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run dns_mail.ps1 DMZH2_DC
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run install_thunderbird.ps1 L4H1_RAC
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run verify_thunderbird.ps1 L4H1_RAC
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run inspect_hmail.ps1         # read-only
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\hmail.py . run logcheck_hmail.ps1        # read-only
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\mail_test.py .                           # send/IMAP/POP3 + no-relay/no-spoof
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\welcome\send_welcome.py . [--only <addr>] [--preview <file.html>]
.\.venv\Scripts\python -I -X utf8 ..\tools\hmailserver\welcome\check_inboxes.py .
```

Add an account: add a `mail/<name>` entry to the credentials file, re-run `configure_hmail.ps1`.

## Verified live 2026-10-20

- Install: service Running (auto) as `NT SERVICE\hMailServer`, listening 25/110/143/587.
- Admin password set; empty password refused afterwards. All 11 accounts validate their password.
- From MC01: AUTH send student1 -> remoteIT on 587, IMAP read, POP3 login OK; unauthenticated
  relay outside->outside refused (550); unauthenticated local sender refused (530).
- RAC: `mail.np.local` resolves, 143/587 open; headless Thunderbird created the preset IMAP account.
- Welcome email (`welcome/`, NP logo inline, no passwords) from admin to the 10 other mailboxes;
  all 10 confirmed in INBOX over IMAP.
- Splunk: `index=mail` receiving from L4H1MAILSERVER, timestamps correct (UTC). `hmailserver:awstats`
  gives src_user / recipient / src / status_code / action (delivered|blocked) / size; `hmailserver`
  gives log_type / protocol / src / user / auth_result (success|failure) / message.

## Splunk notes / open

- `user` (request line) and `auth_result` (server reply) are separate events; correlate per login
  with `... | transaction host session_id log_type` or `stats values(user) values(auth_result) by session_id`.
- No mail alerts yet (candidates: login failures / auto-ban, mail from outside `mail.np.local`, bursts
  to many recipients = phishing blast).

## Rollback

- Thunderbird (RAC): `msiexec /x "C:\ProgramData\LabConsole\hmail\Thunderbird Setup 153.5.0esr.msi" /qn`,
  then delete `C:\Program Files\Mozilla Thunderbird` leftovers (mozilla.cfg, isp, distribution).
- DNS (DC): `Remove-DnsServerResourceRecord -ZoneName np.local -Name mail -RRType A|MX -Force`.
- Firewall (mail server): `Remove-NetFirewallRule -Name LabConsole-hMailServer-Lab`.
- hMailServer: `"C:\Program Files\hMailServer\unins000.exe" /VERYSILENT`, then delete
  `C:\ProgramData\hMailServer` (mail data + logs) if no longer wanted.
- Splunk: remove `lab_hmailserver_inputs` + its serverclass, `lab_mail`, the `[mail]` index and
  `mail` from `srchIndexesDefault` in `tools\splunk-uf\ds`, re-run `deploy_ds.py --force`.
  Pre-change backup: `Backups\20261020-splunk-ds\`.
- Credentials file: entries `hmailserver/Administrator`, `mail/*` (backup
  `config\credentials.example.yaml.bak-20261020-mail`).
