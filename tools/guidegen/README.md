# guidegen — step-by-step Word guides with boxed screenshots

Drives the operator-visible Edge (CDP 127.0.0.1:9222, same window as the NMS/WBM work). Each box
is a temporary page overlay placed from the element's own bounding box, so it sits exactly on the
control; it is removed right after the screenshot. Non-empty password fields are always masked.

| File | What it does |
|---|---|
| `guide.py` | `Guide(page, out).shot(id, text, [locator, All(locator), (locator, label)])` → `<out>/<id>.png` + `steps.json`; `text()` for text-only steps, `meta()` for before/verify/undo |
| `build_docx.py` | `steps.json` + PNGs → A4 .docx (navy headings, gold title rule, framed screenshots). Run with `.venv-docx` (python-docx 1.1.2; kept out of the backend venv) |
| `span_sw_ops.py` | First guide: port mirroring on SW-Ops, done live in phases (`p1`..`p4`, `meta`, `dump`) |
| `splunk_daily.py` | Splunk daily-operations guide, **read-only** tour of Splunk Web at 1440x900 (`diagram`, `c1`..`c4`, `meta`, `look <path>`). Output `Docs/guides/Splunk Daily Operations Guide.docx`; setup diagram is `Docs/guides/splunk-daily/setup.html` rendered to PNG |

`build_docx.py` also takes `sections_before` / `sections_after` (blocks: `p`, `h2`, `bullets`, `numbered`,
`table` + `widths` + `mono`, `image` + `width_cm`, `code`) and a per-step `group` sub-heading.
`guide.shot` crops: `corner` (default), `band` (full-width rows, for dashboards), `viewport`; pass
`scroll=False` when the page is already positioned (tall targets otherwise each scroll the page).

```powershell
.\backend\.venv\Scripts\python -I -X utf8 tools\guidegen\span_sw_ops.py backend Docs\guides\span-scalance <phase>
tools\guidegen\.venv-docx\Scripts\python -I -X utf8 tools\guidegen\build_docx.py Docs\guides\span-scalance "Docs\guides\SCALANCE Port Mirroring (SPAN).docx"
```

Notes from the first run (SCALANCE WBM):
- Many WBM `<input>`s have no `type` attribute: `input[type=text]` misses them; filter on the
  `type` property in JS. Their values are JS-filled, so match on `.value`, not the attribute.
- Tab links are padded with `&nbsp;` — locate them by `href` (`a[href*='mirroring_port.mwp']`).
- Login page has two forms (sidebar + centre); shoot the centre one from a fresh context.
- Capture each step while doing it; don't stage fake "before" states afterwards.
- Splunk 10: header icons have no aria-label; find them by accessible name
  (`get_by_role("button", name=re.compile("^Activity"))`). Search results: `table:has(th)` (the search
  bar is a table too). Triggered Alerts must be opened from inside the app (or `App` = Lab Security),
  else the list hides the LAB alerts. Times display in UTC.
- MC01 has 7.8 GB RAM: with VS Code + two Edge profiles the commit limit was hit on 2026-10-19 and
  Playwright's driver died ("JavaScript heap out of memory" at 12 MB). Operator enabled a page file
  (effective after reboot). Avoid extra `new_context()` windows when memory is short.

## Record: SW-Ops port mirroring (operator, 2026-10-19)
- Backup first: `Backups/20261019-span/SW-Ops/` (CLI + WBM Config/ConfigPack), verified.
- Before: mirroring disabled, no session; P0.8 not connected (P0.1–P0.3 connected).
- Applied via WBM: session 1 (Port Based), destination **P0.8**, sources **P0.1–P0.7 ingress + egress**,
  Mirroring enabled. Monitor Barrier left on (factory default). Left on as requested.
- Verified: WBM read-back after each Set Values; CLI `show monitor session 1` → Both Gi0/1–Gi0/7,
  Destination Gi0/8, Status Active; `Config Change : Saved`. Audit log: `mirroring.*` actions.
- Rollback: `configure terminal` → `no monitor session 1` → `no monitor` → `end` (or WBM: untick
  Mirroring + Set Values, then Select + Delete the session).
