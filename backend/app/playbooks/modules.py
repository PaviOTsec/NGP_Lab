"""Playbook step modules: the extension point.

A module is an async function registered under a name; a playbook step names it as a key:

    from app.playbooks.modules import StepContext, StepOutcome, module

    @module("fortigate_backup")
    async def fortigate_backup(ctx: StepContext, args) -> StepOutcome:
        shell = await ctx.shell()
        res = await shell.run("show full-configuration", timeout=ctx.timeout)
        path = ctx.save_artifact("fortigate.conf", res.stdout)
        return StepOutcome(ok=res.exit_code in (0, None), output=f"saved {path}", artifacts=[path])

Drop such a file into `playbooks/modules/` and it is loaded on the next playbook reload; no
core change. A module that fails to import is reported, never breaks the rest.

Modules get everything through StepContext (session pool, target, run directory, registered
vars, clipboard store) and never reach into app internals beyond that.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core import hyperv, textfmt
from app.core.clipstore import ClipStore
from app.core.pool import SessionPool
from app.core.probe import _port_open
from app.models.inventory import Target
from app.transports.base import CommandResult, Transport, TransportError


@dataclass
class StepOutcome:
    ok: bool
    output: str = ""  # human-readable result (stdout for commands)
    stderr: str = ""
    exit_code: int | None = None
    transport: str = ""
    data: dict[str, Any] = field(default_factory=dict)  # extra fields for `register`
    artifacts: list[str] = field(default_factory=list)  # paths relative to the run dir
    skipped: bool = False


@dataclass
class StepContext:
    pool: SessionPool
    target: Target
    run_id: str
    run_dir: Path
    params: dict[str, Any]
    vars: dict[str, Any]
    credential: str
    timeout: int
    clipstore: ClipStore | None
    log: Callable[[str], None]

    def __post_init__(self) -> None:
        # Canonical form, so containment checks and relative paths agree even when the run
        # folder was given as an 8.3 short path (C:\Users\ADMINI~1\...).
        self.run_dir = self.run_dir.resolve()

    @property
    def target_dir(self) -> Path:
        d = self.run_dir / _safe(self.target.name)
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def shell(self) -> Transport:
        return await self.pool.shell(self.target.name, self.credential)

    async def files(self) -> Transport:
        return await self.pool.file_transport(self.target.name)

    async def hypervisor(self) -> Transport:
        return await self.pool.hypervisor_shell(self.target.name)

    def artifact_path(self, rel: str) -> Path:
        """A path inside this target's run folder. Refuses to escape it."""
        p = (self.target_dir / rel).resolve()
        if not p.is_relative_to(self.run_dir):
            raise TransportError(f"artifact path escapes the run folder: {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_artifact(self, rel: str, content: str | bytes) -> str:
        p = self.artifact_path(rel)
        if isinstance(content, str):
            content = content.encode("utf-8")
        p.write_bytes(content)
        return str(p.relative_to(self.run_dir)).replace("\\", "/")


ModuleFn = Callable[[StepContext, Any], Awaitable[StepOutcome]]
REGISTRY: dict[str, ModuleFn] = {}


def module(name: str) -> Callable[[ModuleFn], ModuleFn]:
    def deco(fn: ModuleFn) -> ModuleFn:
        REGISTRY[name] = fn
        return fn

    return deco


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _from_result(res: CommandResult) -> StepOutcome:
    return StepOutcome(
        ok=res.exit_code in (0, None),
        output=res.stdout,
        stderr=res.stderr,
        exit_code=res.exit_code,
        transport=str(res.transport),
    )


def _args_dict(args: Any, primary: str) -> dict[str, Any]:
    """Allow `module: value` shorthand for the module's main argument."""
    if isinstance(args, dict):
        return args
    return {primary: args}


# ---------------------------------------------------------------------------- built-ins


@module("run")
async def run_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Run a script on the target over its warm shell (PowerShell on Windows, sh on Linux).

        run: Get-Service WinRM
        run: { script: "uname -a" }
    """
    a = _args_dict(args, "script")
    shell = await ctx.shell()
    return _from_result(await shell.run(str(a["script"]), timeout=ctx.timeout))


@module("copy")
async def copy_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Put a file on the target. Source is one of:

        copy: { src: C:\\lab\\tools\\x.zip, dest: C:\\Temp\\x.zip }       # file on MC01
        copy: { content: "...", dest: /tmp/x.sh, eol: lf }               # inline text
        copy: { clip: main/3fa2c1, dest: C:\\Temp\\setup.ps1, eol: crlf } # clipboard item

    `eol` (keep|lf|crlf|auto) applies to text sources; `auto` picks the target OS's endings.
    `encoding` utf8|utf8bom|utf16le. Files are copied byte-exact.
    """
    a = _args_dict(args, "src")
    dest = str(a["dest"])
    t = await ctx.files()
    eol = a.get("eol", "keep")
    if eol == "auto":
        eol = textfmt.eol_for_os(ctx.target.os.value)
    enc = a.get("encoding", "utf8")

    if "content" in a:
        data = textfmt.deliver(str(a["content"]), eol=eol, encoding=enc)
        await t.write_bytes(dest, data)
        return StepOutcome(ok=True, output=f"wrote {len(data)} bytes to {dest}", transport=t.name)
    if "clip" in a:
        if ctx.clipstore is None:
            raise TransportError("clipboard store not available")
        board, _, item_id = str(a["clip"]).partition("/")
        item = ctx.clipstore.get(board, item_id) if item_id else ctx.clipstore.latest(board)
        if item.kind == "text":
            data = textfmt.deliver(ctx.clipstore.read_text(board, item.id), eol=eol,
                                   do_sanitize=bool(a.get("sanitize")), encoding=enc)
            await t.write_bytes(dest, data)
            n = len(data)
        else:
            n = await t.put_file(str(ctx.clipstore.blob_path(board, item.id)), dest)
        return StepOutcome(ok=True, output=f"clipboard {board}/{item.id} -> {dest} ({n} bytes)",
                           transport=t.name)
    n = await t.put_file(str(a["src"]), dest)
    return StepOutcome(ok=True, output=f"copied {n} bytes to {dest}", transport=t.name)


@module("fetch")
async def fetch_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Pull a file from the target into the run folder (MC01).

        fetch: { src: /etc/ssh/sshd_config, dest: sshd_config }   # dest relative to target dir
    """
    a = _args_dict(args, "src")
    src = str(a["src"])
    rel = str(a.get("dest") or os.path.basename(src.replace("\\", "/")) or "fetched")
    local = ctx.artifact_path(rel)
    t = await ctx.files()
    n = await t.get_file(src, str(local))
    path = str(local.relative_to(ctx.run_dir)).replace("\\", "/")
    return StepOutcome(ok=True, output=f"fetched {n} bytes -> {path}", artifacts=[path],
                       transport=t.name)


@module("save")
async def save_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Write text (usually a registered output) into the run folder — the backup primitive.

        save: { content: "{{ vars.config.stdout }}", dest: running-config.txt }
    """
    a = _args_dict(args, "content")
    rel = str(a.get("dest") or "output.txt")
    path = ctx.save_artifact(rel, str(a.get("content", "")))
    return StepOutcome(ok=True, output=f"saved {path}", artifacts=[path])


@module("clip")
async def clip_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Post text to a clipboard board, e.g. to hand a result to whoever is on a VM.

        clip: { content: "{{ vars.ipconfig.stdout }}", board: main, name: "{{ target.name }}" }
    """
    a = _args_dict(args, "content")
    if ctx.clipstore is None:
        raise TransportError("clipboard store not available")
    item = ctx.clipstore.add_text(str(a.get("board", "main")), str(a.get("content", "")),
                                  origin=f"playbook:{ctx.run_id}", name=str(a.get("name", "")))
    return StepOutcome(ok=True, output=f"posted to clipboard as {item.id}", data={"id": item.id})


@module("hyperv")
async def hyperv_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Hyper-V action on the target VM via its hypervisor (always verified, see core.hyperv).

        hyperv: start | shutdown | turnoff | save
        hyperv: { action: checkpoint, type: Standard, name: "pre-{{ run.id }}" }
        hyperv: { action: restore, name: baseline }
        hyperv: { action: delete_checkpoint, name: "pre-{{ run.id }}" }
        hyperv: state
    """
    a = _args_dict(args, "action")
    action = str(a["action"])
    host = await ctx.hypervisor()
    vm = ctx.target.vm_name or ctx.target.name
    if action in ("start", "shutdown", "turnoff", "save"):
        st = await hyperv.set_power(host, vm, action)
        return StepOutcome(ok=True, output=f"{vm}: {st.state}", data={"state": st.state},
                           transport=host.name)
    if action == "state":
        st = await hyperv.get_vm_state(host, vm)
        return StepOutcome(ok=True, output=f"{vm}: {st.state}", data={"state": st.state},
                           transport=host.name)
    if action == "checkpoint":
        snap = await hyperv.create_checkpoint(host, vm, checkpoint_type=str(a.get("type", "Production")),
                                              name=a.get("name"))
        return StepOutcome(ok=True, output=f"{snap.name} ({snap.snapshot_type})",
                           data={"name": snap.name, "type": snap.snapshot_type}, transport=host.name)
    if action == "restore":
        st = await hyperv.restore_checkpoint(host, vm, str(a["name"]))
        return StepOutcome(ok=True, output=f"{vm} restored to {a['name']}: {st.state}",
                           data={"state": st.state}, transport=host.name)
    if action == "delete_checkpoint":
        await hyperv.delete_checkpoint(host, vm, str(a["name"]))
        return StepOutcome(ok=True, output=f"deleted checkpoint {a['name']}", transport=host.name)
    raise TransportError(f"unknown hyperv action: {action}")


@module("wait_for")
async def wait_for_module(ctx: StepContext, args: Any) -> StepOutcome:
    """Wait until a TCP port on the target answers (e.g. after a reboot).

        wait_for: 5985
        wait_for: { port: 22, timeout: 300, delay: 10 }
    """
    a = _args_dict(args, "port")
    port, limit, delay = int(a["port"]), int(a.get("timeout", 300)), int(a.get("delay", 0))
    if not ctx.target.address:
        raise TransportError(f"{ctx.target.name} has no address to wait on")
    await asyncio.sleep(delay)
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if await _port_open(ctx.target.address, port, 2.0):
            return StepOutcome(ok=True, output=f"{ctx.target.address}:{port} is open")
        await asyncio.sleep(3)
    return StepOutcome(ok=False, output=f"{ctx.target.address}:{port} still closed after {limit}s")


@module("pause")
async def pause_module(ctx: StepContext, args: Any) -> StepOutcome:
    """pause: 30   — wait N seconds."""
    seconds = float(_args_dict(args, "seconds")["seconds"])
    await asyncio.sleep(seconds)
    return StepOutcome(ok=True, output=f"paused {seconds:g}s")
