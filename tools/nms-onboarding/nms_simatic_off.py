import json
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
CHECKS = """() => [...document.querySelectorAll('input[type=checkbox]')].filter(c => c.offsetParent).map(c => {
    let e = c, label = '';
    for (let i = 0; i < 5 && e && !label; i++) { e = e.parentElement; label = e ? (e.innerText||'').trim().split('\\n')[0] : ''; }
    return {label: label.slice(0, 60), checked: c.checked}; })"""
def open_group(pg):
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SIMATIC monitoring settings", exact=True).first.click(); pg.wait_for_timeout(2500)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front(); open_group(pg)
    # untick from the most specific option up to the master switch
    for lbl in ("SIMATIC monitoring including assigned devices and SIMATIC alarm messages",
                "SIMATIC monitoring including assigned devices and SIMATIC event messages",
                "SIMATIC monitoring of assigned devices", "SIMATIC monitoring"):
        t = pg.get_by_text(lbl, exact=True).first
        box = t.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]//input[@type='checkbox']").first
        if box.is_enabled() and box.is_checked():
            box.uncheck(force=True); pg.wait_for_timeout(500)
    print("before save:", json.dumps(pg.evaluate(CHECKS)))
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_timeout(4000)
    open_group(pg)
    print("after reload:", json.dumps(pg.evaluate(CHECKS)))
