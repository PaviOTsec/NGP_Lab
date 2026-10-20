# Lab Console

A lab management suite for a workgroup Hyper-V OT/ICS lab, run from the management
workstation (MC01):

- **Console**: warm sessions to every host and VM. Terminals, file transfer, fan-out
  commands, and Hyper-V power and checkpoints, with the fastest available transport chosen
  automatically (the direct link first, the Hyper-V link after).
- **Playbooks**: Ansible-style YAML jobs over the inventory, such as "back up every device"
  or "training reset". You run them from a web page; each run keeps its own logs and
  artifacts. A new step type is one Python file.
- **Shared clipboard**: a cl1p.net-style page that every VM opens in a browser, or reaches
  with `curl` / `Invoke-WebRequest`. Text and files move between machines byte-exact, and
  you can choose LF or CRLF and clean up Word-style characters, so commands don't get mangled.
- **Agent access** (next): coding agents operate the VMs through the same API.

> **Status:** the code has unit tests and a live smoke test on MC01, but has **not** yet
> been run against the real lab hosts. See `CLAUDE.md`, `docs/REQUIREMENTS.md`, and grep for
> `TODO(mc01)`.

## Layout

```
├── CLAUDE.md                 # context + hard rules for anyone (incl. Claude Code) editing this
├── backend/app/
│   ├── main.py               # two listeners: console (token) + clipboard (VM-facing)
│   ├── core/                 # pool, hyperv, credentials, clipstore, textfmt, vmtext, audit
│   ├── transports/           # Transport interface + winrm / ssh / smb / psdirect
│   ├── playbooks/            # schema, templating, step modules, runner, builtin/*.yaml
│   ├── routes/               # console API; board.py is shared with the clipboard server
│   └── clip_page/index.html  # the page the VMs open
├── frontend/                 # Vite + React + TS console (xterm.js), NP navy/gold theme
├── config/                   # inventory / settings / credentials examples
├── playbooks/                # your playbooks (YAML) + modules/ (custom step types)
└── docs/                     # REQUIREMENTS.md, HANDOFF.md, legacy/LabConnect.ps1
```

## Running (on MC01)

**One-time setup:**

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e .        # or from a bundled wheel folder offline

cd ..\frontend
npm install
npm run build                                       # the backend serves frontend/dist

cd ..\config
copy inventory.example.yaml inventory.yaml         # the observed lab; already in place on MC01
copy settings.example.toml settings.toml           # optional; defaults are fine
```

One one-time step needs an elevated PowerShell. TrustedHosts is not needed: the console
uses its own WinRM client, and it verifies each host's identity itself before logging in.

```powershell
# Let the VMs reach the shared clipboard
New-NetFirewallRule -DisplayName "Lab Console clipboard" -Direction Inbound -Protocol TCP -LocalPort 8766 -Action Allow
```

Write a credentials file in the format of `config/credentials.example.yaml`. Keep it
wherever you like, and never commit it.

**Each time:**

```powershell
backend\.venv\Scripts\labconsole.exe
```

This opens the console in your browser. Choose the credentials file (upload it, or type its
path on MC01, which is remembered), and the dashboard connects to every reachable target.

On any VM, open `http://<MC01 address>:8766/` for the shared clipboard. MC01's DMZ address
is `10.1.20.56`.

## Development

```powershell
cd backend
$env:LABCONSOLE_TESTING = "1"
.\.venv\Scripts\python -m pytest -q
```

Windows-only transports are imported lazily, so unit tests run against mocked transports
(`tests/mocks.py`) on any OS.

## Security posture (v1)

- The console binds to localhost and needs the per-launch token on every call, plus a
  Host-header check.
- The clipboard server is open to the lab network and serves only the clipboard. Anything
  pasted there is readable by every machine that can reach MC01, including the attacker VMs.
- Credentials are a plaintext file chosen at startup. Hardening is deliberately deferred.
- `HyperVAdmin` is never widened. Host-level steps declare the separate admin credential.
- Vendor appliance images are never modified.
