# Playbooks

Drop a YAML file here and it appears on the console's **Playbooks** screen the next time
the screen is opened. A file here with the same `name` as a built-in playbook
(`backend/app/playbooks/builtin/`) replaces the built-in one.

```yaml
name: collect-hosts-file
title: Collect hosts files
description: Save every Windows guest's hosts file into the run folder.
targets: { kind: guest, os: windows }      # kind / os / segment / vendor / tags / names
params:
  - { name: note, type: string, default: "", label: Note for the file name }
confirm: false
concurrency: 8
steps:
  - name: Read hosts
    run: Get-Content C:\Windows\System32\drivers\etc\hosts -Raw
    register: hosts
  - name: Save
    save: { content: "{{ vars.hosts.stdout }}", dest: "hosts-{{ params.note }}.txt" }
```

**Step keys.** Every step names exactly one module, and can also set any of these:

- `name`
- `register` keeps the step's result for later steps, as `{{ vars.<name>.stdout }}`
- `credential`: `default`, or `host-admin` for hypervisor-level work
- `when`, e.g. `{ os: linux }`
- `ignore_errors`
- `timeout`, in seconds

**Templates.** These values can be substituted into step arguments:

- `{{ params.x }}`
- `{{ target.name }}` and the target's other inventory fields
- `{{ vars.r.stdout }}`
- `{{ run.id }}`, `{{ run.dir }}`
- `{{ now }}`

Filters: `| ps` (PowerShell-quoted), `| sh` (shell-quoted), `| json`, `| lower`, `| upper`, `| trim`.
A misspelled variable fails the step instead of running half a command.

**Built-in modules:**

| Module | What it does |
|---|---|
| `run` | Script over the target's shell (PowerShell on Windows, sh on Linux/network devices) |
| `copy` | Put a file on the target from MC01 (`src`), inline `content`, or a clipboard item (`clip: main/3fa2c1`); `eol: auto` converts line endings for the target OS |
| `fetch` | Pull a file from the target into the run folder |
| `save` | Write text (usually a registered output) into the run folder. This is how backups are written |
| `clip` | Post text to a clipboard board |
| `hyperv` | `start`, `shutdown`, `turnoff`, `save`, `state`, `checkpoint`, `restore`, `delete_checkpoint`. Each one reads the VM back afterwards to verify it |
| `wait_for` | Wait for a TCP port on the target |
| `pause` | Wait N seconds |

**Runs.** Every run gets its own folder under `%LOCALAPPDATA%\LabConsole\runs\<run-id>\`. It holds:

- `run.json`
- one log file per step
- whatever the steps saved: backups, fetched files, reports

## Custom modules (`playbooks/modules/*.py`)

To add a new step type, add one Python file to `playbooks/modules/`. It's loaded when the playbook list reloads. If the file is broken, it's listed as an error and the other modules keep working.

```python
from app.playbooks.modules import StepContext, StepOutcome, module

@module("hello")
async def hello(ctx: StepContext, args) -> StepOutcome:
    shell = await ctx.shell()                     # warm session for ctx.target
    res = await shell.run(f"echo hello {args}", timeout=ctx.timeout)
    path = ctx.save_artifact("hello.txt", res.stdout)
    return StepOutcome(ok=res.exit_code in (0, None), output=res.stdout, artifacts=[path])
```

`StepContext` exposes the following:

- **Target and run:** `target` (the inventory entry), `params`, `vars`, `run_id`, `run_dir`, `timeout`, `credential`, `clipstore`
- **Sessions:** `shell()`, `files()`, `hypervisor()`
- **Run-folder files:** `artifact_path(rel)`, `save_artifact(rel, content)`
- **Logging:** `log(msg)`, which adds a live progress line
