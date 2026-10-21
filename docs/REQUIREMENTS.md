# Lab Console — Requirements

This is the on-disk copy of the requirements for Claude Code. It mirrors the shared
requirements doc. Where this and `CLAUDE.md` disagree, this file wins; flag the conflict.

## 1. Purpose and scope

A lab management suite on MC01: a web console that opens sessions, moves files, and runs
Hyper-V operations across the OT lab in one or two clicks; an Ansible-like playbook engine
customised for this lab's scenarios (e.g. back up every network device from one page); a
shared clipboard every VM can open; and (next) an API surface through which coding agents
operate the VMs under the operator's supervision. It replaces the manual PowerShell-remoting
workflow and the shelved `LabConnect.ps1` launcher (in `docs/legacy/`).

**Goals**

1. Warm, reusable sessions to every reachable host and guest, opened in parallel when credentials load.
2. The fastest available transport chosen automatically per operation (§3).
3. One place for terminals, file transfer, fan-out commands, VM power, and checkpoints.
4. Credentials from a plaintext file the operator chooses in the app (§5).
5. An extension model: playbooks (YAML) and step modules (Python) added without touching the core (§6).
6. A shared clipboard that keeps text formatting and files intact between any two machines (§4a).
7. Agent access over the same API, audited per actor (§11).

**Phasing.** v1 targets the setup phase: lab firewalls allow everything and MC01 is
dual-homed into the DMZ. v2 hardens without rewriting (§10). **Users.** One operator in v1;
multi-user and RBAC are out of scope.

## 2. Environment and constraints

Runs on MC01 (Windows client OS), manages workgroup Hyper-V hosts over NTLM. Every choice
must work without a domain trust between MC01 and the lab.

- **MC01**: client OS, one interactive session, has internet. NIC1 → management switch;
  NIC2 → DMZ 10.1.20.0/24, no default gateway, static routes to lab subnets via 10.1.20.254.
- **Hypervisors**: DMZ-HOST-1/2, L4-HOST-1, L2-HOST-1. Server 2022, workgroup, local accounts.
- **Hypervisor account**: `<HOST>\HyperVAdmin`, Hyper-V Administrators + Remote Management
  Users. Not a full admin.
- **WinRM auth**: NTLM; targets must be in MC01's `TrustedHosts`.
- **Domain**: np.local (NetBIOS NP), DC 10.1.20.17. Some guests domain-joined; MC01 is not.
- **Firewalls**: SCALANCE, FortiGate, Palo Alto; allow-all during setup.
- **Guests**: no internet; some reachable only via the hypervisor over VMBus.
- **Guest OS mix**: Windows Server, Ubuntu 22.04 (INS), Kali, vendor appliances.

**Hard constraints**

- No changes to vendor appliance images. Power/checkpoint/web-UI only; no agents/SSH/WinRM.
- Never widen HyperVAdmin; host-level work uses a separate host-local Administrator credential.
- No runtime internet/CDN dependency; bundle all assets.
- No admin rights to run day to day. One-time setup (TrustedHosts) is shown, not applied silently.

## 3. Architecture and transports

A local backend on MC01 holds the loaded credentials and a pool of warm connections; the browser is only
a view. Speed comes from never paying connection setup twice and from using bulk protocols
for bulk data.

**Stack**: Python 3.13 (>=3.12) + FastAPI backend; React + Vite + TS frontend; xterm.js over
WebSocket. pypsrp (PSRP), asyncssh (SSH/SFTP), smbprotocol (SMB), pywinpty (local PTY).

**Speed principles**

1. Open all sessions in parallel when credentials load, keep them alive, reuse them.
2. Never spawn a fresh `powershell.exe` per action.
3. Bulk data over SMB or SFTP, never chunked through WinRM unless nothing else is reachable.
4. Pick transport per target+operation, with a fallback order. **The direct link is always
   tried first** when the target has an address and its route isn't `via-host`; the Hyper-V
   link (PowerShell Direct / `Copy-VMFile` via the hypervisor) only after that.

| Operation | Target | Primary | Fallback |
|---|---|---|---|
| Shell | Hypervisor | WinRM(PSRP) as HyperVAdmin, warm runspace | admin-cred session for host-level work |
| Shell | Windows guest, reachable | WinRM(PSRP), warm runspace | PowerShell Direct (`-VMName`) on its hypervisor |
| Shell | Windows guest, isolated | PowerShell Direct on its hypervisor | — |
| Shell | Linux guest | SSH, one persistent conn, multiplexed | VMConnect console |
| Shell | Network device | SSH (vendor CLI) | — |
| Fan-out | Mixed | parallel over warm sessions | per-target as above |
| File | Windows guest/host | SMB to admin share | `Copy-Item -ToSession`, then `Copy-VMFile` via host |
| File | Linux guest | SFTP over the open SSH conn | `Copy-VMFile` where guest services allow |
| Power/checkpoint | Any VM | WinRM to hypervisor, Hyper-V cmdlets | — |
| Console | Any VM | native `vmconnect.exe`, network-only creds | — |
| RDP | Windows guest | native `mstsc.exe`, short-lived cmdkey | enhanced session via VMConnect |
| Web UI | Appliance | open URL in a new tab | — |

**Native launches.** VMConnect and Hyper-V Manager authenticate over WMI/DCOM as the caller,
which workgroup hosts reject. Launch with network-only credentials (the programmatic
`runas /netonly`: `CreateProcessWithLogonW` + `LOGON_NETCREDENTIALS_ONLY`). For `mstsc`,
stage a `cmdkey` entry and delete it once the window opens.

## 4. Functional requirements (v1)

IDs are stable so commits/tests can reference them.

- **FR-01** Load credentials: operator chooses the credentials file in the app (upload, or a path on MC01 that is remembered). *(Must)*
- **FR-02** On load, open sessions to all reachable targets in parallel with per-target progress. *(Must)*
- **FR-03** Inventory from YAML (hosts, VMs, address, OS, segment, credential ref, access policy, tags). *(Must)*
- **FR-04** Discovery: merge live `Get-VM` data (state, uptime, IPs, checkpoints) into the view. *(Must)*
- **FR-05** Dashboard grouped by segment (L5, L4, DMZ, L3, Plantbus, L2, L1, Mgmt); one card per
  host, VM, network device and L1 field device. L2 and below are badged OT and handled with care
  (CLAUDE.md rule 13). *(Must)*
- **FR-06** Reachability probe every 10 s (TCP 5985, 22, 445, 3389, 443 as relevant) → chips.
  L1 field devices (PLCs, IO, IEDs, RTU) are never probed. *(Must)*
- **FR-07** One-click terminal per target in a tab, using the warm session; multiple tabs + split. *(Must)*
- **FR-08** Multi-select + run one command/script in parallel; results table (output, exit, duration). *(Must)*
- **FR-09** File transfer drag-and-drop to one/many targets, and download; transport per §3; throughput shown. *(Must)*
- **FR-10** Hyper-V per VM: start, shut down, turn off, save, checkpoint, list/restore/delete checkpoint. *(Must)*
- **FR-11** Checkpoint creation chooses Production/Standard, then verifies the resulting snapshot type. *(Must)*
- **FR-12** Launch native VMConnect, mstsc, and appliance web UIs from the card. *(Must)*
- **FR-13** Confirmation dialog for destructive actions, naming targets. *(Must)*
- **FR-14** Audit log of every action (time, target, action, transport, result), append-only JSONL. *(Must)*
- **FR-15** Disconnect: unload credentials and close every session. *(Must)*
- **FR-16** Command palette (Ctrl+K). *(Should)*
- **FR-17** Playbooks: YAML multi-step jobs with parameters, target selectors, live progress, run history and per-run artifacts (§6). *(Must)*
- **FR-18** Host health panel: WinRM state/start type, disk free (`Win32_LogicalDisk`), time sync. *(Should)*
- **FR-19** Restore a named group of VMs to a named checkpoint in one action (training reset). *(Should)*
- **FR-20** Forward the audit log to Splunk HEC when configured. *(Could)*
- **FR-21** Topology view from the inventory, segments as zones. *(Could)*

### 4a. Shared clipboard (cl1p.net-style)

A browser page every VM opens to move text and files between machines without commands
getting mangled across operating systems. Served by MC01 on its own listener (§8).

- **CB-01 Board page** — `http://<MC01>:8766/b/<board>`: paste text (tabs/spacing kept,
  Tab key inserts a tab), drop or paste files (screenshots included), live list of items
  newest first; boards are just names. Plain ES5, no external assets (IE11/old Edge OK). *(Must)*
- **CB-02 Exact storage** — items stored byte-exact with SHA-256; text gets an EOL badge
  (CRLF/LF/mixed) and a warning badge when it contains Word-style characters. *(Must)*
- **CB-03 Delivery per OS** — on copy/download/fetch the operator picks: as stored, Linux
  (LF) or Windows (CRLF); optionally fix curly quotes/long dashes/NBSP/zero-width chars;
  optionally UTF-8 BOM (Windows PowerShell 5.1 `.ps1`). Files are always byte-exact. *(Must)*
- **CB-04 Terminal access** — headless VMs use curl / Invoke-WebRequest: `GET /r/<board>[/<id>]`
  (with `?eol=&sanitize=&encoding=`), `POST /api/clip/<board>/text` (raw body),
  `POST /api/clip/<board>/upload?name=` (raw file). Each item shows ready-to-copy commands. *(Must)*
- **CB-05 Session-backed helpers (console)** — send a board item to a VM as a file over the
  lab session (converted for the VM's OS, read back and checksum-verified); pull a VM file
  onto the board; type text or a credential's password into a VM's virtual keyboard via
  `Msvm_Keyboard.TypeText` (logon screens, consoles, appliances; ASCII/US only, length cap). *(Must)*

A direct `Set-Clipboard`-over-WinRM push is explicitly **not** used: it fills session 0's
clipboard, which the interactive user never sees, and Linux servers have no GUI clipboard.

## 5. Credentials

- A **plaintext YAML file** (format `config/credentials.example.yaml`): entry name →
  username, password, optional SSH key (inline or a key-file path).
- Chosen **in the app** at startup: uploaded from the browser, or a path on MC01 (the path
  is remembered for next launch). Kept in backend memory while loaded; "Disconnect" unloads
  it and closes every session.
- The inventory refers to entries by name (`credential:`, `admin_credential:`).
- Per-host `<HOST>\HyperVAdmin` for Hyper-V; a separate host-local Administrator entry for
  steps declared `credential: host-admin`. Domain guests use `NP\<user>` over NTLM by IP.
- Secret hardening (vault, USB key, DPAPI) is **deliberately out of scope for now**. Never
  commit a credentials file; keep passwords out of the audit log and error text.
## 6. Extensibility — playbooks and step modules

- **Playbooks** (declarative): one YAML file per playbook in `playbooks/` (built-ins in
  `backend/app/playbooks/builtin/`, overridable by name), reloaded whenever the list opens.
  Fields: name, title, description, targets (kind/os/segment/vendor/tags/names), params,
  confirm, concurrency, steps. Each step names one module plus optional `register`,
  `credential` (default | host-admin), `when`, `ignore_errors`, `timeout`. Arguments are
  templated (`{{ params.x }}`, `{{ target.name }}`, `{{ vars.r.stdout }}`, quoting filters).
- **Runs** execute in the background: targets in parallel (bounded), steps in order, a target
  stops at its first failure. Live progress by polling; every run gets a folder with
  `run.json`, one log per step, and artifacts (backups, fetched files, reports).
- **Step modules** (code): a Python file in `playbooks/modules/` registering
  `@module("name")`. Modules get the session pool, target, run folder, registered vars and
  clipboard store through `StepContext`. A failing module file is reported, never stops
  startup. Built-ins: run, copy, fetch, save, clip, hyperv, wait_for, pause.
- Network-device backups will be step modules per vendor (dialect from inventory `vendor`);
  designed per playbook type, not up front.
- Later hook: an `ansible` step type running a playbook from WSL against the same inventory.
## 7. UI and theme

Ngee Ann Polytechnic navy/gold, colour only (no logo/name). Palette is CSS custom
properties, one source of truth. Navy base, gold a sparing accent (≤10% of any screen),
gold never text-on-white and never a status colour, status uses green/orange/red. Dark
theme default; light theme from the same tokens.

Navy `#003C77` (from NP CMYK 100/55/10/48); gold `#F2B300` (approximation — confirm against
NP brand material, no official hex published). Layout: left nav (Dashboard, Terminals, Fan-out, Playbooks,
Clipboard, Files, Hyper-V, Audit, Settings); dashboard lanes top-to-bottom L5/L4/DMZ/L3/Plantbus/L2/L1/Mgmt;
VM card with state dot, reachability chips, last-checkpoint age, quick actions; terminals
tabbed/splittable with segment-coloured stripe; Ctrl+K palette; Inter + JetBrains Mono,
bundled.

## 8. Non-functional requirements

- Warm-up: all reachable targets connected within 10 s of loading credentials (~15 targets, parallel).
- Terminal opens on a warm target within 1.5 s.
- Fan-out total ≤ slowest target + 0.5 s.
- File transfer ≥ 80% of raw SMB throughput (Windows); SFTP (Linux).
- UI responds within 100 ms; long work runs in the background with progress.
- Connect timeout 5 s/target; one unreachable target never blocks others.
- Dropped sessions reconnect with backoff; state shown on the card.
- Two listeners in one process. Console: 127.0.0.1 by default, Host-header check, per-launch
  token on every route (anti-DNS-rebinding). Clipboard: 0.0.0.0:8766 so VMs can reach it,
  serving only the clipboard board (needs an inbound firewall rule on MC01).
- Windows 10/11 client, Python 3.13 venv, no admin to run (one-time firewall rule aside).
- One start script launches backend + browser; deps installable from a local wheel folder.
- Audit log append-only, rotated at 10 MB, records the actor (operator / agent / playbook run).
- Type hints throughout; transport behind an interface with mock unit tests; integration
  tests against one real host behind an env guard.

## 9. Known gotchas (handle by design)

- `Set-VM` can return no error and not apply → always `-Passthru` + read-back + verify.
- `CheckpointType Disabled` = "no preference"; `Checkpoint-VM` then makes Standard → verify
  `SnapshotType` with `Get-VMSnapshot` after every checkpoint.
- Production checkpoints need healthy VSS in the guest → surface VSS status before offering.
- `Get-Volume` Access Denied under HyperVAdmin → `Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'`.
- HyperVAdmin is limited → actions declare the credential class; host-level uses the admin entry.
- WinRM can start before the NIC and self-stop (clean exit 0) → show start type; offer the
  delayed-auto fix as an action.
- WinRM/NTLM needs TrustedHosts on MC01 → check against inventory, show the exact command.
- Hyper-V Manager/VMConnect use WMI/DCOM as caller → launch with network-only creds.
- `Copy-VMFile` reads source from the hypervisor, not MC01 → stage to the host first.
- PowerShell Direct not for Linux guests → never offer.
- Clipboard paste never works at a guest logon screen → use Type-into-VM instead.
- Appliance images set `fDisableCdm = 1` on purpose → never change; no drive-mapping for appliances.
- SMB with built-in Administrator disabled → use the host's designated admin account; keep the
  mapping alive for the whole transfer.
- Hosts fail NTP until SINEC INS serves time → show clock skew; it affects logs and certs.
- Windows PowerShell 5.1 `ConvertTo-Json` writes enums as integers (`State: 2`) → cast enum
  fields to `[string]` on the host before serialising.
- PSRP returns objects; `str()` of one is its type name → format object output with
  `Out-String` but pass plain strings through untouched (file chunks, JSON).
- Text-mode file I/O on Windows rewrites `\n` to `\r\n` → all remote file I/O is binary;
  line-ending conversion only happens on request, in one place.
- Windows PowerShell 5.1 sends request bodies as cp1252 without an explicit charset → the
  clipboard decodes BOM, then UTF-8, then cp1252.

## 10. Hardening path (v2)

Every target carries a `route` field: `direct`, `via-host` (PowerShell Direct or `Copy-VMFile`
through its hypervisor), or `via-jump`. In v1 most routes are `direct`. Hardening changes
routes in configuration, tightens firewall rules to MC01's address, and finally removes NIC2.
No application code should change.

## 11. Agent access (next)

Coding agents (Claude Code and similar) operate the lab through the same API the console
uses, so they get the same transport selection, verification and audit trail:

- An MCP server and a `labctl` CLI, both thin clients of the console API, exposing: list
  targets, run a command, read/write files, power/checkpoint, run a playbook and poll it,
  read/write the clipboard.
- Every call is audited with the actor (`agent:<name>`); playbook runs record their actor.
- The operator supervises agents directly; no extra permission tiers in v1. Hard rules still
  apply to agents (appliance images untouched, HyperVAdmin never widened).