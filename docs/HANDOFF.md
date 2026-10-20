# Handoff notes

## State as of 2026-10-09

**Built and tested off-lab.** That means 48 unit tests, plus a live smoke test of both
listeners on MC01 against unroutable TEST-NET addresses.

- **Credentials.** A plaintext YAML file chosen in the app, either uploaded or loaded from a
  remembered path. KeePass, DPAPI and the USB key are gone.
- **Two listeners.**
  - Console: 127.0.0.1:8765, needs the token.
  - Clipboard: 0.0.0.0:8766, serves the board only. Verified reachable on MC01's DMZ
    address, and verified to expose no console API.
- **Session pool.** Tries the direct link first, then PowerShell Direct through the
  hypervisor. `host-admin` gets its own session and is never a silent fallback.
- **Hyper-V.**
  - Power actions verify the read-back state and are idempotent.
  - Checkpoint delete is verified.
  - **Fixed:** PS 5.1 serialised enums as ints, which would have failed every verification
    on the real hosts.
- **WinRM output formatting.** Objects are formatted like a console. Plain strings (file
  chunks, JSON) pass through exactly.
- **Byte-exact remote file I/O on every transport.** SMB used to translate LF to CRLF in
  text mode. WinRM and PowerShell Direct gained file read/write, which they didn't have.
- **Shared clipboard.**
  - Board page that works in ES5/IE11.
  - curl/iwr API.
  - Per-OS delivery: line endings, Word-character cleanup, BOM.
  - Console panel: send a board item to a VM (checksum-verified), pull a file from a VM,
    type into a VM.
- **Playbook engine.** Replaces the actions engine.
  - YAML playbooks and Python step modules.
  - Background runs with live progress.
  - A run folder per run, with logs and artifacts.
  - Built-ins: `host-health`, `winrm-delayed-start`, `system-snapshot`, `training-reset`.
- **Frontend screens.** Credentials, Dashboard, Terminals, Fan-out, Playbooks, Clipboard,
  Audit.
- A snapshot of the original scaffold was taken before the refactor, because there's no git
  on MC01.

## First checks against the real lab (in order)

1. Copy `config/inventory.example.yaml` to `config/inventory.yaml` and fill in the host IPs.
   Write a credentials file and load it in the app.
2. Confirm sessions to one hypervisor (WinRM) and DMZH1-SinecINS (SSH). Check the Dashboard
   transport label on each card.
3. Run the **Host health snapshot** playbook on the four hypervisors. Check that the disks
   and WinRM fields read correctly; this exercises the enum-to-string and output-formatting
   paths.
4. Power cycle a non-critical guest from the dashboard. Confirm the read-back state.
5. Create a **Production** checkpoint on a Windows guest. Confirm the verified type is
   reported, and that it refuses if the result comes back Standard.
6. Open `http://10.1.20.56:8766/` from a DMZ VM. Paste a multi-line script, then fetch it on
   a Linux VM with the "Linux: print" command and on Windows with "PowerShell: print".
7. From the console Clipboard screen, send a file to a Windows guest. Confirm "sha256
   verified" and that the transport is SMB, not WinRM.
8. Type a short string into a VM at its **logon screen** with "Type into VM".

## Still open — grep `TODO(mc01)`

- **Native launches (FR-12):** VMConnect and mstsc with network-only credentials. Not written.
- **Copy-VMFile fallback** for isolated guests: stage the file on the host first.
- **SSH host keys** are not pinned (`known_hosts=None`).
- **WinRM concurrency.** Is one runspace pool per target enough under fan-out plus an open
  terminal? Check on the real hosts.
- **Native `$LASTEXITCODE`.** Native exe failures such as `sc.exe` aren't turned into step
  failures yet. A playbook should verify with a follow-up step, as `winrm-delayed-start`
  does.
- **Agent access:** the MCP server and `labctl` CLI.
- **Network-device modules,** designed per playbook type. Some vendor CLIs need an
  interactive shell channel instead of SSH exec.
