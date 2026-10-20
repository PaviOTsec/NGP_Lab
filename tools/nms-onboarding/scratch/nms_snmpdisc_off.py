import json
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
GRID = """() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
    .map(c => (c.getAttribute('col-id')||'') + '=' + c.innerText.trim().replace(/\\s+/g,' ')).filter(x => !x.endsWith('=')).join(' | ')).filter(Boolean)"""
def open_group(pg):
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front(); open_group(pg)
    for name in ("SNMP Settings V1", "SNMP Settings V2"):
        cb = pg.locator(f"div[role=row]:has([col-id=name]:text-is('{name}')) input[type=checkbox]")
        if cb.count() == 0:
            idx = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('{name}')); return r ? r.getAttribute('row-index') : null; }}""")
            cb = pg.locator(f"div[role=row][row-index='{idx}'] input[type=checkbox]")
        print(name, "checkbox count:", cb.count())
        cb.first.check(force=True); pg.wait_for_timeout(400)
    pg.get_by_text("Disable", exact=True).last.click(); pg.wait_for_timeout(1500)
    rows = pg.evaluate(GRID); print("before save:", rows)
    if all(r.startswith("status=Disabled") for r in rows) and len(rows) == 2:
        pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_timeout(4000)
    else:
        print("unexpected -> not saved")
    open_group(pg); print("after reload:", pg.evaluate(GRID))
    pg.screenshot(path=OUT + r"\nms_snmp_discovery_disabled.png", full_page=True)
