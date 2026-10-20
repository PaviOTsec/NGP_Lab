import re
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    cands = pg.locator("*:visible").filter(has_text=re.compile(r"^\s*Stop network scan\s*$"))
    leaf = [i for i in range(cands.count()) if cands.nth(i).evaluate("e => e.children.length === 0 || [...e.children].every(c => !(c.innerText||'').trim())")]
    print("candidates:", cands.count(), "leaf:", len(leaf), [cands.nth(i).evaluate("e => e.tagName + '.' + e.className") for i in leaf])
    if len(leaf) == 1:
        el = cands.nth(leaf[0])
        el.click(); pg.wait_for_timeout(3000)
        pg.screenshot(path=OUT + r"\nms_after_stop_click.png")
        body = " ".join(pg.inner_text("body").split())
        print("after click:", re.findall(r"(?i)[^.]{0,100}(stop|confirm|are you sure)[^.]{0,100}", body)[:4])
