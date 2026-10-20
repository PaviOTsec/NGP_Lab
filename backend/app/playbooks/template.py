"""Tiny, strict templating for playbook step arguments.

    {{ params.delay_ms }}            value lookup by dotted path
    {{ target.name }}                the current target's inventory fields
    {{ vars.disk.stdout }}           output registered by an earlier step (`register: disk`)
    {{ run.id }} {{ run.dir }} {{ now }}
    {{ params.user | ps }}           filters: ps (PowerShell single-quoted literal),
                                     sh (POSIX shell-quoted), json, lower, upper, trim

Unknown names raise, so a typo fails the step loudly instead of running a half-built command.
Values are substituted raw unless a quoting filter is used.
"""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

_EXPR = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*((?:\|\s*[a-z]+\s*)*)\}\}")

_FILTERS = {
    "ps": lambda v: "'" + str(v).replace("'", "''") + "'",
    "sh": lambda v: shlex.quote(str(v)),
    "json": lambda v: json.dumps(v),
    "lower": lambda v: str(v).lower(),
    "upper": lambda v: str(v).upper(),
    "trim": lambda v: str(v).strip(),
}


class TemplateError(Exception):
    pass


def _lookup(ctx: dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif hasattr(cur, part) and not part.startswith("_"):
            cur = getattr(cur, part)
        else:
            raise TemplateError(f"unknown template variable: {path}")
    return cur


def render_str(text: str, ctx: dict[str, Any]) -> Any:
    """Render one string. A string that is exactly one expression keeps the value's type."""
    whole = _EXPR.fullmatch(text.strip()) if text.strip().startswith("{{") else None
    if whole and not whole.group(2).strip():
        return _lookup(ctx, whole.group(1))

    def sub(m: re.Match) -> str:
        val = _lookup(ctx, m.group(1))
        for name in [f.strip() for f in m.group(2).split("|") if f.strip()]:
            if name not in _FILTERS:
                raise TemplateError(f"unknown template filter: {name}")
            val = _FILTERS[name](val)
        return "" if val is None else str(val)

    return _EXPR.sub(sub, text)


def render(value: Any, ctx: dict[str, Any]) -> Any:
    """Render strings anywhere inside dicts/lists."""
    if isinstance(value, str):
        return render_str(value, ctx) if "{{" in value else value
    if isinstance(value, dict):
        return {k: render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    return value
