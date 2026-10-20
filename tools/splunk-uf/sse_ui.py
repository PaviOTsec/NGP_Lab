"""Drive Splunk Web (Security Essentials setup) in the operator-visible Edge (CDP 127.0.0.1:9222).

usage: python -I -X utf8 tools/splunk-uf/sse_ui.py <backend_dir> <out_dir> <step> [arg]
  login                  identity check (NTLM: 10.1.20.15 must be DMZH1SIEM) -> Splunk Web login
  goto <path>            open http://10.1.20.15:8000/en-US<path>
  inspect                headings, visible modal text, visible buttons/links + a screenshot
  click "<exact text>"   click the ONE visible button/link whose text is exactly this
Each step is one small action so every screen is looked at before anything is pressed.
Exceptions print their type only (Playwright call logs echo typed values).
"""
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
STEP = sys.argv[3]
ARG = sys.argv[4] if len(sys.argv) > 4 else ""
sys.path.insert(0, str(BACKEND))
from app.core import identity  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = "10.1.20.15"
BASE = f"http://{HOST}:8000/en-US"
OUT.mkdir(parents=True, exist_ok=True)

INSPECT_JS = """() => {
  const vis = el => !!(el.offsetParent || el.getClientRects().length) && getComputedStyle(el).visibility !== 'hidden';
  const t = el => (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
  const modals = [...document.querySelectorAll('.modal, [role=dialog], .ui-dialog')].filter(vis).map(m => t(m).slice(0, 700));
  const heads = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(t).filter(x => x).slice(0, 12);
  const btns = [...document.querySelectorAll('button, a.btn, input[type=button], input[type=submit], [role=button]')]
      .filter(vis).map(t).filter(x => x && x.length < 60);
  return {url: location.href, title: document.title, heads, modals, buttons: [...new Set(btns)].slice(0, 60)};
}"""


def page_for(ctx):
    pg = next((x for x in ctx.pages if x.url.startswith(f"http://{HOST}:8000")), None)
    if pg is None:
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.bring_to_front()
    return pg


def shot(pg, name):
    path = OUT / f"{time.strftime('%H%M%S')}_{name}.png"
    pg.screenshot(path=str(path))
    return path


if STEP == "login":  # before Playwright's own event loop starts
    identity.check("DMZH1SIEM", asyncio.run(identity.probe_identity(HOST, timeout=8)), HOST)
    print("identity: 10.1.20.15 answers as DMZH1SIEM")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    pg = page_for(ctx)
    try:
        if STEP == "login":
            cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("splunk/admin")
            pg.goto(f"{BASE}/account/login", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(2000)
            if pg.locator("input[name=username]").count():
                pg.fill("input[name=username]", cred.username)
                pg.click("input[name=password]")
                pg.keyboard.type(cred.password or "", delay=15)
                pg.keyboard.press("Enter")
                pg.wait_for_load_state("domcontentloaded", timeout=60000)
                pg.wait_for_timeout(4000)
            print("logged in" if "/account/login" not in pg.url else "still on the login page", "->", pg.url)
        elif STEP == "goto":
            pg.goto(BASE + ARG, wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(6000)
            print("at", pg.url)
        elif STEP == "dom":  # outerHTML of the smallest element containing ARG, and its parent
            print(pg.evaluate("""(t) => { const els = [...document.querySelectorAll('body *')].filter(e => (e.innerText||'').includes(t));
                const el = els[els.length - 1]; if (!el) return 'not found';
                return (el.parentElement || el).outerHTML.slice(0, 1500); }""", ARG))
            sys.exit(0)
        elif STEP == "clicksel":  # click the ONE visible element matching this CSS selector
            loc = pg.locator(ARG)
            hits = [i for i in range(loc.count()) if loc.nth(i).is_visible()]
            if len(hits) != 1:
                sys.exit(f"expected exactly 1 visible match for {ARG!r}, found {len(hits)} - not clicking")
            loc.nth(hits[0]).click()
            pg.wait_for_timeout(5000)
            print(f"clicked {ARG}")
        elif STEP in ("maprows", "notdetection"):
            # Content Mapping modal rows: name, status, mapped content. `notdetection <regex>` presses
            # "Not A Detection" on every row whose saved-search name matches the regex (and nothing else).
            import re as _re
            import json as _json
            rows = pg.evaluate("""() => [...document.querySelectorAll('tr[data-searchname]')]
                .map((r, i) => { const td = [...r.querySelectorAll('td')].map(c => (c.innerText || '').trim().replace(/\\s+/g, ' '));
                  return {i, name: r.getAttribute('data-searchname'), status: td[2] || '', mapped: td[3] || ''}; })""")
            pat = _re.compile(ARG) if STEP == "notdetection" else None
            for r in rows:
                print(f"  {r['status'][:16]:16} | {r['name'][:70]:70} | {r['mapped'][:60]}")
            print(f"{len(rows)} rows")
            if pat:
                todo = [r for r in rows if pat.search(r["name"])]
                print(f"pressing 'Not A Detection' on {len(todo)} row(s) matching {ARG!r}")
                for r in todo:
                    btn = pg.locator(f"tr[data-searchname={_json.dumps(r['name'])}] div.action_markIrrelevant")
                    if btn.count() == 1:
                        btn.first.scroll_into_view_if_needed()
                        btn.first.click()
                        pg.wait_for_timeout(700)
                    else:
                        print(f"   skipped (button not unique/visible): {r['name']}")
            sys.exit(0)
        elif STEP == "rowsearch":  # press "Search" on the (first) mapping row with this saved-search name
            import json as _json
            btn = pg.locator(f"tr[data-searchname={_json.dumps(ARG)}] div.action_findOther").first
            btn.scroll_into_view_if_needed()
            btn.click()
            pg.wait_for_timeout(4000)
            print(f"pressed Search on {ARG!r}")
            STEP = "inspect"
        elif STEP == "type":  # type into the focused / last visible text box of the top modal
            box = pg.locator(".modal:visible input[type=text], [role=dialog] input[type=text]").last
            box.click()
            box.fill("")
            pg.keyboard.type(ARG, delay=60)
            # SSE 3.8 quirk: its type-ahead calls doSearch() with no results (always "Nothing found");
            # only Enter runs index.search(<text>).
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(4000)
            print(f"typed {ARG!r}")
            STEP = "inspect"
        elif STEP == "pick":  # click the ONE search-result tile whose title is exactly ARG
            ids = pg.evaluate("""(title) => [...document.querySelectorAll('.showcaseItemTile[data-showcaseid]')]
                .filter(t => t.offsetParent && [...t.querySelectorAll('h1,h2,h3,h4,a,span,div')]
                    .some(e => (e.innerText || '').trim() === title))
                .map(t => t.getAttribute('data-showcaseid'))""", ARG)
            ids = sorted(set(ids))
            if len(ids) != 1:
                sys.exit(f"expected exactly 1 tile titled {ARG!r}, found {len(ids)}: {ids[:5]} - not clicking")
            pg.locator(f".showcaseItemTile[data-showcaseid='{ids[0]}']").first.click()
            pg.wait_for_timeout(4000)
            print(f"picked {ARG!r} ({ids[0]})")
            sys.exit(0)
        elif STEP == "top":  # scroll to the top of the page
            pg.evaluate("() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0; }); }")
            pg.wait_for_timeout(1500)
            STEP = "inspect"
        elif STEP == "click":
            loc = pg.locator("button, a, input[type=button], input[type=submit], [role=button]").filter(has_text=ARG)
            hits = [i for i in range(loc.count()) if loc.nth(i).is_visible()
                    and (loc.nth(i).inner_text() or loc.nth(i).get_attribute("value") or "").strip() == ARG]
            if len(hits) != 1:
                sys.exit(f"expected exactly 1 visible '{ARG}', found {len(hits)} - not clicking")
            loc.nth(hits[0]).click()
            pg.wait_for_timeout(5000)
            print(f"clicked '{ARG}'")
        if STEP in ("inspect", "goto", "click", "clicksel", "login"):
            info = pg.evaluate(INSPECT_JS)
            print(f"title: {info['title']}\nurl: {info['url']}\nheadings: {info['heads']}")
            for m in info["modals"]:
                print(f"MODAL: {m}")
            print(f"buttons: {info['buttons']}")
            print("screenshot:", shot(pg, STEP))
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"step {STEP} failed: {type(exc).__name__}")
