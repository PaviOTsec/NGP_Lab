"""Annotated screenshots for step-by-step guides, captured from the operator-visible Edge (CDP).

Boxes are a temporary DOM overlay placed from each target element's own bounding box, so they
always sit exactly on the element (no pixel guessing). The overlay is removed right after the
screenshot. Non-empty password fields are always masked.

Steps are kept in <out>/steps.json (keyed by step id, so a re-run replaces its own steps);
build_docx.py turns that folder into a Word document.

    from guide import Guide
    g = Guide(page, out_dir, title="...", intro="...")
    g.shot("02", "Open **Layer 2 > Mirroring**.", [nav_l2, nav_mirroring])
    g.text("09", "Done.")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

OVERLAY_ID = "__guidegen_overlay"
BOX = "#d4001a"  # red box, numbered gold badge

_DRAW = """([rects, id, color]) => {
  const root = document.createElement('div');
  root.id = id;
  root.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none';
  rects.forEach((r, i) => {
    const b = document.createElement('div');
    b.style.cssText = `position:fixed;left:${r.x - 4}px;top:${r.y - 4}px;width:${r.width + 8}px;` +
      `height:${r.height + 8}px;border:3px solid ${color};border-radius:4px;box-sizing:border-box`;
    root.appendChild(b);
    if (r.label) {
      const n = document.createElement('div');
      n.textContent = r.label;
      // on the box's top-left corner: never covers a label to the right of a small checkbox
      n.style.cssText = `position:fixed;left:${Math.max(0, r.x - 16)}px;top:${Math.max(0, r.y - 16)}px;min-width:20px;` +
        `height:20px;padding:0 4px;border-radius:10px;background:${color};color:#fff;` +
        'font:bold 12px/20px Arial,sans-serif;text-align:center;box-sizing:border-box';
      root.appendChild(n);
    }
  });
  document.body.appendChild(root);
}"""
_CLEAR = "(id) => { const e = document.getElementById(id); if (e) e.remove(); }"


class All:
    """Target: one box around every element the locator matches (e.g. a block of checkboxes)."""

    def __init__(self, locator: Any) -> None:
        self.locator = locator

    def bounding_box(self) -> dict[str, float] | None:
        boxes = [b for i in range(self.locator.count()) if (b := self.locator.nth(i).bounding_box())]
        if not boxes:
            return None
        x0, y0 = min(b["x"] for b in boxes), min(b["y"] for b in boxes)
        x1 = max(b["x"] + b["width"] for b in boxes)
        y1 = max(b["y"] + b["height"] for b in boxes)
        return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


class Guide:
    def __init__(self, page: Any, out: Path, title: str = "", intro: str = "") -> None:
        self.page, self.out = page, Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest = self.out / "steps.json"
        self.data: dict[str, Any] = (json.loads(self.manifest.read_text(encoding="utf-8"))
                                     if self.manifest.exists() else {"steps": {}})
        if title:
            self.data["title"] = title
        if intro:
            self.data["intro"] = intro

    def meta(self, **kw: Any) -> None:
        """Extra document fields (e.g. subtitle, notes, appendix) read by build_docx.py."""
        self.data.update(kw)
        self._save()

    def text(self, sid: str, text: str, group: str = "") -> None:
        self.data["steps"][sid] = {"text": text, **({"group": group} if group else {})}
        self._save()

    def shot(self, sid: str, text: str, targets: Sequence[Any] = (), *, labels: bool | None = None,
             min_w: int = 900, min_h: int = 420, pad: int = 60, page: Any = None,
             clip: dict[str, float] | None = None, crop: str = "corner", group: str = "",
             scroll: bool = True) -> Path:
        """Box each target (locator, All(locator), or (either, label)), screenshot, record the step.

        crop="corner": from the page's top-left corner to just past the targets (at least
        min_w x min_h), so the header and menu stay in view. crop="band": full width, only the
        rows the targets occupy (+pad) - for wide dashboards. crop="viewport": whole viewport.
        group: start a new sub-heading in the document before this step.
        scroll=False: the caller has already positioned the page (targets taller than the
        viewport would otherwise each scroll it in turn).
        """
        pg = page or self.page
        items = [t if isinstance(t, tuple) else (t, None) for t in targets]
        if labels is None:
            labels = len(items) > 1
        rects = []
        for i, (loc, label) in enumerate(items):
            if scroll and not isinstance(loc, All):
                loc.first.scroll_into_view_if_needed(timeout=5000)
            bb = loc.bounding_box() if isinstance(loc, All) else loc.first.bounding_box()
            if bb is None:
                raise RuntimeError(f"step {sid}: target {i + 1} not visible")
            rects.append({**bb, "label": label or (str(i + 1) if labels else "")})
        vw = pg.viewport_size or pg.evaluate("() => ({width: innerWidth, height: innerHeight})")
        right = max([min_w] + [int(r["x"] + r["width"]) + pad for r in rects])
        bottom = max([min_h] + [int(r["y"] + r["height"]) + pad for r in rects])
        if clip is None and crop == "band" and rects:
            top = max(0, int(min(r["y"] for r in rects)) - pad)
            clip = {"x": 0, "y": top, "width": vw["width"],
                    "height": min(vw["height"], int(max(r["y"] + r["height"] for r in rects)) + pad) - top}
        elif clip is None and crop == "viewport":
            clip = {"x": 0, "y": 0, "width": vw["width"], "height": vw["height"]}
        clip = clip or {"x": 0, "y": 0, "width": min(right, vw["width"]), "height": min(bottom, vw["height"])}
        secrets = pg.locator("input[type=password]")
        masked = [secrets.nth(i) for i in range(secrets.count())
                  if secrets.nth(i).is_visible() and secrets.nth(i).input_value()]
        pg.evaluate(_DRAW, [rects, OVERLAY_ID, BOX])
        try:
            img = self.out / f"{sid}.png"
            pg.screenshot(path=str(img), clip=clip, mask=masked, animations="disabled")
        finally:
            pg.evaluate(_CLEAR, OVERLAY_ID)
        self.data["steps"][sid] = {"text": text, "image": img.name, **({"group": group} if group else {})}
        self._save()
        return img

    def _save(self) -> None:
        self.manifest.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
