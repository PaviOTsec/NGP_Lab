"""Playbook registry and runner.

Runs execute in the background: targets in parallel (bounded by `concurrency`), steps per
target in order, stopping a target at its first failing step unless `ignore_errors`. Every
step writes its full output to the run folder and an audit event; the in-memory event list
feeds live progress (the UI and agents poll it).

Run folder (settings.playbooks.runs_dir):
    <run-id>/run.json                       summary: playbook, params, per-target step results
    <run-id>/<target>/NN-<step>.log         full output of each step
    <run-id>/<target>/...                   artifacts written by steps (fetch/save/backups)
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import secrets
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.audit import AuditLog
from app.core.clipstore import ClipStore
from app.core.pool import SessionPool
from app.models.inventory import Inventory, Target
from app.playbooks import modules as mods
from app.playbooks.model import Playbook
from app.playbooks.template import TemplateError, render
from app.transports.base import TransportError

OUTPUT_KEEP = 64 * 1024  # chars of output kept in run.json per step; the .log has it all


class PlaybookRegistry:
    """Loads playbooks (YAML) and user step modules (Python) from disk."""

    def __init__(self, playbook_dirs: list[Path], module_dirs: list[Path]) -> None:
        self._playbook_dirs = playbook_dirs
        self._module_dirs = module_dirs
        self._playbooks: dict[str, Playbook] = {}
        self.errors: list[str] = []
        self.reload()

    def reload(self) -> None:
        self.errors = []
        self._load_modules()
        known = set(mods.REGISTRY)
        found: dict[str, Playbook] = {}
        for d in self._playbook_dirs:
            if not d.exists():
                continue
            for path in sorted([*d.glob("*.yaml"), *d.glob("*.yml")]):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                    pb = Playbook.from_yaml_dict(data, default_name=path.stem,
                                                 source_file=str(path), known_modules=known)
                    if pb.name not in found:  # first dir wins: user playbooks shadow built-ins
                        found[pb.name] = pb
                except Exception as exc:  # noqa: BLE001 - a bad file must not hide the rest
                    self.errors.append(f"{path.name}: {exc}")
        self._playbooks = found

    def _load_modules(self) -> None:
        for d in self._module_dirs:
            if not d.exists():
                continue
            for path in sorted(d.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                name = f"labconsole_user_module_{path.stem}"
                try:
                    spec = importlib.util.spec_from_file_location(name, path)
                    assert spec and spec.loader
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[name] = mod
                    spec.loader.exec_module(mod)  # registers via @module(...)
                except Exception as exc:  # noqa: BLE001
                    self.errors.append(f"modules/{path.name}: {exc}")

    def all(self) -> list[Playbook]:
        return list(self._playbooks.values())

    def get(self, name: str) -> Playbook | None:
        return self._playbooks.get(name)

    @staticmethod
    def targets_for(pb: Playbook, inventory: Inventory) -> list[Target]:
        return [t for t in inventory.all() if t.configured and pb.targets.matches(t)]


# ---------------------------------------------------------------------------- run records


@dataclass
class StepRecord:
    index: int
    name: str
    module: str
    status: str = "pending"  # pending | running | ok | failed | skipped | cancelled
    started: str = ""
    duration_ms: int = 0
    transport: str = ""
    exit_code: int | None = None
    output: str = ""
    stderr: str = ""
    error: str = ""
    artifacts: list[str] = field(default_factory=list)
    log: str = ""  # relative path of the full-output log


@dataclass
class TargetRun:
    target: str
    status: str = "pending"  # pending | running | ok | failed | cancelled
    steps: list[StepRecord] = field(default_factory=list)


@dataclass
class Run:
    id: str
    playbook: str
    title: str
    params: dict[str, Any]
    actor: str
    dir: str
    status: str = "running"  # running | ok | failed | cancelled
    started: str = ""
    finished: str = ""
    targets: dict[str, TargetRun] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    task: asyncio.Task | None = field(default=None, repr=False)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for tr in self.targets.values():
            counts[tr.status] = counts.get(tr.status, 0) + 1
        return {"id": self.id, "playbook": self.playbook, "title": self.title,
                "status": self.status, "started": self.started, "finished": self.finished,
                "actor": self.actor, "targets": counts}

    def to_dict(self, *, events_since: int | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            k: getattr(self, k) for k in
            ("id", "playbook", "title", "params", "actor", "dir", "status", "started", "finished")
        }
        d["targets"] = {name: asdict(tr) for name, tr in self.targets.items()}
        if events_since is not None:
            d["events"] = [e for e in self.events if e["seq"] > events_since]
        return d


# ---------------------------------------------------------------------------- runner


class RunManager:
    def __init__(self, *, runs_dir: Path, audit: AuditLog, clipstore: ClipStore | None,
                 default_concurrency: int = 8) -> None:
        self.runs_dir = runs_dir
        self.audit = audit
        self.clipstore = clipstore
        self.default_concurrency = default_concurrency
        self._runs: dict[str, Run] = {}

    def start(self, pb: Playbook, *, pool: SessionPool, targets: list[Target],
              params: dict[str, Any], actor: str = "operator") -> Run:
        resolved = pb.resolve_params(params)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        run_id = f"{stamp}-{pb.name}-{secrets.token_hex(2)}"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run = Run(id=run_id, playbook=pb.name, title=pb.title, params=resolved, actor=actor,
                  dir=str(run_dir), started=_now())
        for t in targets:
            run.targets[t.name] = TargetRun(
                target=t.name,
                steps=[StepRecord(index=i, name=s.name, module=s.module)
                       for i, s in enumerate(pb.steps, 1)],
            )
        self._runs[run_id] = run
        self._event(run, None, None, "run", f"started on {len(targets)} target(s) by {actor}")
        run.task = asyncio.create_task(self._execute(run, pb, pool, targets))
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent runs: live ones from memory, finished ones from their run.json."""
        out: dict[str, dict[str, Any]] = {r.id: r.summary() for r in self._runs.values()}
        if self.runs_dir.exists():
            for d in sorted(self.runs_dir.iterdir(), reverse=True)[: limit * 2]:
                if d.name in out or not (d / "run.json").exists():
                    continue
                try:
                    data = json.loads((d / "run.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                counts: dict[str, int] = {}
                for tr in data.get("targets", {}).values():
                    counts[tr["status"]] = counts.get(tr["status"], 0) + 1
                out[d.name] = {k: data.get(k) for k in
                               ("id", "playbook", "title", "status", "started", "finished", "actor")}
                out[d.name]["targets"] = counts
        return sorted(out.values(), key=lambda r: r["id"], reverse=True)[:limit]

    def load(self, run_id: str) -> dict[str, Any] | None:
        """A run's full record, live or from disk."""
        if run := self._runs.get(run_id):
            return run.to_dict(events_since=0)
        path = self.runs_dir / run_id / "run.json"
        if not path.exists() or "/" in run_id or "\\" in run_id or ".." in run_id:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def cancel(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.task is None or run.task.done():
            return False
        run.task.cancel()
        return True

    # --- internals ---

    def _event(self, run: Run, target: str | None, step: str | None, status: str, message: str) -> None:
        run.events.append({"seq": len(run.events) + 1, "ts": _now(), "target": target,
                           "step": step, "status": status, "message": message[:500]})

    async def _execute(self, run: Run, pb: Playbook, pool: SessionPool, targets: list[Target]) -> None:
        sem = asyncio.Semaphore(pb.concurrency or self.default_concurrency)

        async def one(t: Target) -> None:
            async with sem:
                await self._run_target(run, pb, pool, t)

        try:
            await asyncio.gather(*(one(t) for t in targets))
            failed = any(tr.status == "failed" for tr in run.targets.values())
            run.status = "failed" if failed else "ok"
        except asyncio.CancelledError:
            run.status = "cancelled"
            for tr in run.targets.values():
                if tr.status in ("pending", "running"):
                    tr.status = "cancelled"
                    for s in tr.steps:
                        if s.status in ("pending", "running"):
                            s.status = "cancelled"
        finally:
            run.finished = _now()
            self._event(run, None, None, run.status, f"run {run.status}")
            self.audit.record(action=f"playbook:{pb.name}", target="-", result=run.status,
                              detail={"run": run.id, "actor": run.actor, "targets": len(targets)})
            self._persist(run)

    async def _run_target(self, run: Run, pb: Playbook, pool: SessionPool, t: Target) -> None:
        tr = run.targets[t.name]
        tr.status = "running"
        run_dir = Path(run.dir)
        tvars: dict[str, Any] = {}
        ctx_base = {
            "params": run.params,
            "target": t.model_dump(mode="json"),
            "run": {"id": run.id, "dir": run.dir, "started": run.started},
            "now": time.strftime("%Y%m%d-%H%M%S"),
            "vars": tvars,
        }
        for step, rec in zip(pb.steps, tr.steps):
            if not step.applies_to(t):
                rec.status = "skipped"
                continue
            rec.status, rec.started = "running", _now()
            self._event(run, t.name, step.name, "running", f"{step.module}")
            started = time.monotonic()
            ctx = mods.StepContext(
                pool=pool, target=t, run_id=run.id, run_dir=run_dir, params=run.params,
                vars=tvars, credential=step.credential, timeout=step.timeout,
                clipstore=self.clipstore,
                log=lambda m, tn=t.name, sn=step.name: self._event(run, tn, sn, "log", m),
            )
            try:
                args = render(step.args, ctx_base)
                outcome = await asyncio.wait_for(mods.REGISTRY[step.module](ctx, args),
                                                 timeout=step.timeout + 30)
            except asyncio.CancelledError:
                rec.status = "cancelled"
                raise
            except (TransportError, TemplateError, ValueError, KeyError, OSError,
                    asyncio.TimeoutError) as exc:
                outcome = mods.StepOutcome(ok=False, stderr=_err(exc))
            except Exception as exc:  # noqa: BLE001 - a buggy module fails its step, not the run
                outcome = mods.StepOutcome(ok=False, stderr=_err(exc) + "\n" + traceback.format_exc())

            rec.duration_ms = int((time.monotonic() - started) * 1000)
            rec.transport, rec.exit_code = outcome.transport, outcome.exit_code
            rec.output, rec.stderr = outcome.output[:OUTPUT_KEEP], outcome.stderr[:OUTPUT_KEEP]
            rec.artifacts = outcome.artifacts
            rec.log = self._write_log(run_dir, t.name, rec, outcome)
            rec.status = "ok" if outcome.ok else "failed"
            if not outcome.ok:
                rec.error = _last_line(outcome.stderr or outcome.output) or "failed"
            if step.register_as:
                tvars[step.register_as] = {"stdout": outcome.output, "stderr": outcome.stderr,
                                        "exit_code": outcome.exit_code, "ok": outcome.ok,
                                        **outcome.data}
            self._event(run, t.name, step.name, rec.status,
                        rec.error if not outcome.ok else _first_line(outcome.output))
            self.audit.record(action=f"playbook:{pb.name}:{step.module}", target=t.name,
                              transport=rec.transport, result=rec.status,
                              detail={"run": run.id, "step": step.name, "actor": run.actor})
            if not outcome.ok and not step.ignore_errors:
                tr.status = "failed"
                for later in tr.steps[rec.index:]:
                    later.status = "skipped"
                return
        tr.status = "ok"

    def _write_log(self, run_dir: Path, target: str, rec: StepRecord, o: mods.StepOutcome) -> str:
        d = run_dir / mods._safe(target)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{rec.index:02d}-{mods._safe(rec.name)[:60]}.log"
        body = o.output
        if o.stderr:
            body += ("\n" if body and not body.endswith("\n") else "") + "--- stderr ---\n" + o.stderr
        path.write_text(body, encoding="utf-8")
        return str(path.relative_to(run_dir)).replace("\\", "/")

    def _persist(self, run: Run) -> None:
        try:
            (Path(run.dir) / "run.json").write_text(
                json.dumps(run.to_dict(events_since=0), indent=1, default=str), encoding="utf-8")
        except OSError:
            pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _first_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0][:300] if lines else ""


def _last_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1][:300] if lines else ""


def _err(exc: BaseException) -> str:
    msg = str(exc) or type(exc).__name__
    return f"{type(exc).__name__}: {msg}" if not isinstance(exc, TransportError) else msg
