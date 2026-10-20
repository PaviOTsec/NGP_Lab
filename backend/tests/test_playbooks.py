"""Playbook schema, templating, registry loading and the background runner."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.audit import AuditLog
from app.models.inventory import Inventory
from app.playbooks import modules as mods
from app.playbooks.engine import PlaybookRegistry, RunManager
from app.playbooks.model import Playbook
from app.playbooks.template import TemplateError, render
from tests.mocks import make, result

BUILTIN = Path(__file__).resolve().parents[1] / "app" / "playbooks" / "builtin"

INV = Inventory.model_validate({
    "hypervisors": [{"name": "H1", "kind": "hypervisor", "os": "windows", "segment": "DMZ",
                     "address": "10.0.0.1", "credential": "c"}],
    "targets": [
        {"name": "WIN", "kind": "guest", "os": "windows", "segment": "DMZ", "host": "H1",
         "vm_name": "WIN", "address": "10.0.0.2", "credential": "c", "tags": ["lab"]},
        {"name": "LIN", "kind": "guest", "os": "linux", "segment": "L4", "host": "H1",
         "vm_name": "LIN", "address": "10.0.0.3", "credential": "c"},
    ],
})


class StubPool:
    """Per-target mock shells; `fail` makes a target's commands exit non-zero."""

    def __init__(self, fail: set[str] = frozenset()):
        self.shells = {t.name: make(t.name, responses=[("", result(f"out-{t.name}",
                                                                   exit_code=1 if t.name in fail else 0))])
                       for t in INV.all()}

    async def shell(self, name, cred_class="default"):  # noqa: ARG002
        return self.shells[name]

    async def file_transport(self, name):
        return self.shells[name]

    async def hypervisor_shell(self, name):  # noqa: ARG002
        return self.shells["H1"]


def _pb(steps: list[dict], **kw) -> Playbook:
    return Playbook.from_yaml_dict({"steps": steps, **kw}, default_name="t", source_file="",
                                   known_modules=set(mods.REGISTRY))


async def _run(tmp_path, pb, targets, pool=None, params=None):
    mgr = RunManager(runs_dir=tmp_path / "runs", audit=AuditLog(tmp_path / "a.jsonl"), clipstore=None)
    run = mgr.start(pb, pool=pool or StubPool(), targets=targets, params=params or {})
    await asyncio.wait_for(run.task, 5)
    return run, mgr


# --- schema / templating -------------------------------------------------------------------


def test_unknown_module_fails_at_load():
    with pytest.raises(ValueError, match="unknown module"):
        _pb([{"name": "x", "nonesuch": 1}])


def test_step_must_name_exactly_one_module():
    with pytest.raises(ValueError, match="exactly one module"):
        _pb([{"run": "a", "save": "b"}])


def test_template_values_filters_and_strictness():
    ctx = {"params": {"n": 5, "who": "O'Brien"}, "target": {"name": "WIN"}}
    assert render("{{ params.n }}", ctx) == 5  # whole-expression keeps type
    assert render("x={{params.n}} t={{ target.name | lower }}", ctx) == "x=5 t=win"
    assert render("{{ params.who | ps }}", ctx) == "'O''Brien'"
    assert render("{{ params.who | sh }}", ctx) == "'O'\"'\"'Brien'"
    assert render({"a": ["{{ target.name }}"]}, ctx) == {"a": ["WIN"]}
    with pytest.raises(TemplateError):
        render("{{ params.typo }}", ctx)


def test_selector_and_when():
    pb = _pb([{"run": "x", "when": {"os": "linux"}}], targets={"kind": "guest", "tags": ["lab"]})
    assert [t.name for t in INV.all() if pb.targets.matches(t)] == ["WIN"]
    assert pb.steps[0].applies_to(INV.by_name("LIN"))
    assert not pb.steps[0].applies_to(INV.by_name("WIN"))


def test_builtin_playbooks_all_load():
    reg = PlaybookRegistry([BUILTIN], [])
    assert not reg.errors, reg.errors
    assert {"host-health", "winrm-delayed-start", "system-snapshot", "training-reset"} <= {
        p.name for p in reg.all()}


def test_user_module_drop_in(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "hello.py").write_text(
        "from app.playbooks.modules import module, StepOutcome\n"
        "@module('hello')\n"
        "async def hello(ctx, args):\n"
        "    return StepOutcome(ok=True, output='hi ' + str(args))\n", encoding="utf-8")
    (tmp_path / "modules" / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    (tmp_path / "greet.yaml").write_text("steps:\n  - hello: world\n", encoding="utf-8")
    reg = PlaybookRegistry([tmp_path], [tmp_path / "modules"])
    assert reg.get("greet") is not None
    assert any("broken.py" in e for e in reg.errors)  # reported, not fatal


# --- runner --------------------------------------------------------------------------------


async def test_run_register_save_and_artifacts(tmp_path):
    pb = _pb([
        {"name": "Get config", "run": "show run", "register": "cfg"},
        {"name": "Save", "save": {"content": "{{ vars.cfg.stdout }}", "dest": "{{ target.name }}.cfg"}},
    ])
    run, mgr = await _run(tmp_path, pb, [INV.by_name("WIN"), INV.by_name("LIN")])
    assert run.status == "ok"
    assert (Path(run.dir) / "WIN" / "WIN.cfg").read_text() == "out-WIN"
    assert (Path(run.dir) / "LIN" / "LIN.cfg").read_text() == "out-LIN"
    saved = json.loads((Path(run.dir) / "run.json").read_text())
    assert saved["targets"]["WIN"]["steps"][1]["artifacts"] == ["WIN/WIN.cfg"]
    assert mgr.history()[0]["id"] == run.id


async def test_failure_stops_that_target_only(tmp_path):
    pb = _pb([{"run": "a"}, {"run": "b"}])
    run, _ = await _run(tmp_path, pb, [INV.by_name("WIN"), INV.by_name("LIN")],
                        pool=StubPool(fail={"WIN"}))
    assert run.status == "failed"
    assert run.targets["WIN"].status == "failed"
    assert [s.status for s in run.targets["WIN"].steps] == ["failed", "skipped"]
    assert run.targets["LIN"].status == "ok"


async def test_ignore_errors_and_when_skip(tmp_path):
    pb = _pb([{"run": "a", "ignore_errors": True}, {"run": "b", "when": {"os": "linux"}}])
    run, _ = await _run(tmp_path, pb, [INV.by_name("WIN")], pool=StubPool(fail={"WIN"}))
    assert run.targets["WIN"].status == "ok"
    assert [s.status for s in run.targets["WIN"].steps] == ["failed", "skipped"]


async def test_params_are_coerced_and_required(tmp_path):
    pb = _pb([{"run": "echo {{ params.n }}"}],
             params=[{"name": "n", "type": "int", "default": 3}, {"name": "must", "required": True}])
    with pytest.raises(ValueError, match="required"):
        await _run(tmp_path, pb, [INV.by_name("WIN")])
    pool = StubPool()
    run, _ = await _run(tmp_path, pb, [INV.by_name("WIN")], pool=pool, params={"must": "x"})
    assert run.params == {"n": 3, "must": "x"}
    assert "echo 3" in pool.shells["WIN"].calls[0]


async def test_cancel(tmp_path):
    pb = _pb([{"pause": 30}])
    mgr = RunManager(runs_dir=tmp_path / "runs", audit=AuditLog(tmp_path / "a.jsonl"), clipstore=None)
    run = mgr.start(pb, pool=StubPool(), targets=[INV.by_name("WIN")], params={})
    await asyncio.sleep(0.05)
    assert mgr.cancel(run.id)
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 5)
    assert run.status == "cancelled"
    assert run.targets["WIN"].steps[0].status == "cancelled"
