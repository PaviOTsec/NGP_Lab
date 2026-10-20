# Sysmon on the lab Windows hosts (2026-10-16)

Microsoft Sysinternals **Sysmon 15.22** on all 9 Windows hosts with a forwarder or Splunk
(LogServer, MSSQL, DC, ADWSUS, MaintServer, RAC, Spare/Office Workstation, MailServer, SIEM).
Events go to Splunk index **`sysmon`** (XML) and feed the CIM Endpoint data model, which most
Splunk research (ESCU) detections use. Never on appliances / power-only VMs.

## Files

| File | What |
|---|---|
| `incoming/Sysmon/Sysmon64.exe` | from `https://download.sysinternals.com/files/Sysmon.zip`; Authenticode **Microsoft Windows Publisher** (checked on MC01 and on each host) |
| `incoming/sysmonconfig-15.21.xml` | sysmon-modular release `configs-a45dedb13a43` (2026-10-14) "Balanced", sha256 from the release `SHA256SUMS` |
| `incoming/sysmonconfig-excludes-only-15.21.xml` | same release, for reference (its ProcessCreate exclude list = Balanced's) |
| `sysmonconfig-lab.xml` (+ `.sha256`) | **the config in use** — built by `build_config.py` |
| `build_config.py` | Balanced, but ProcessCreate logs **every** process start minus the 178 noise excludes, plus: Splunk's `splunk-*.exe` helpers when `splunkd.exe` is the parent |
| `push_sysmon.py` | install (`-accepteula -i`) or `--update-config` (`-c`); verifies service, driver (`sc query SysmonDrv`), events, and the loaded `ConfigHash` |

Why the lab build: Balanced only logs process creation for an include list, so e.g. `setspn.exe`
was never recorded and the ESCU process detections couldn't fire. Positive test 2026-10-16:
`setspn -Q HOST/DMZH1LOGSERVER*` on LogServer → caught by *ESCU - ServicePrincipalNames
Discovery with SetSPN* once the lab config was loaded.

Revocation checks and DNS lookups are off in the config (offline hosts: they would stall).

## Usage

```powershell
.\backend\.venv\Scripts\python -I -X utf8 tools\sysmon\build_config.py          # after changing the build
.\backend\.venv\Scripts\python -I -X utf8 tools\sysmon\push_sysmon.py backend default --dry-run
.\backend\.venv\Scripts\python -I -X utf8 tools\sysmon\push_sysmon.py backend default --update-config
```

## Forwarder access to the Sysmon log

The Sysmon channel is readable only by SYSTEM, Administrators, Backup/Server Operators and
**Event Log Readers**. The forwarders run as `NT SERVICE\SplunkForwarder` (except the DC: LocalSystem),
so `tools\splunk-uf\uf_event_log_readers.ps1` added that account to Event Log Readers (6 hosts) and
`uf_sysmon_channel_acl.ps1` granted it read on the channel on **DMZH2_ADWSUS**, which has no
Event Log Readers group (several BUILTIN groups are missing there). A Sysmon *reinstall* may reset
the channel ACL on ADWSUS — re-run that script.

## Uninstall

`C:\Windows\Sysmon64.exe -u` on a host (removes service + driver; the event log stays).
