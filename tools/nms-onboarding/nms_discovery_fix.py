"""Starter Set: untick 'Discovery of NAT / routers' (save), then read SIMATIC monitoring settings."""
import json
from playwright.sync_api import sync_playwright

BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
CHECKS = """() => [...document.querySelectorAll('input[type=checkbox]')].filter(c => c.offsetParent).map(c => {
    let e = c, label = '';
    for (let i = 0; i < 5 && e && !label; i++) { e = e.parentElement; label = e ? (e.innerText||'').trim().split('\\n')[0] : ''; }
    return {label: label.slice(0, 70), checked: c.checked}; })"""


def open_group(pg, group):
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    pg.get_by_text(group, exact=True).first.click()
    pg.wait_for_timeout(2500)


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    open_group(pg, "Discovery settings")
    print("discovery before:", json.dumps(pg.evaluate(CHECKS)))
    label = pg.get_by_text("Discovery of NAT / routers", exact=True).first
    box = label.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]//input[@type='checkbox']").first
    if box.is_checked():
        box.uncheck(force=True)
        pg.wait_for_timeout(800)
        pg.get_by_role("button", name="Save", exact=True).click()
        pg.wait_for_timeout(4000)
    open_group(pg, "Discovery settings")
    print("discovery after reload:", json.dumps(pg.evaluate(CHECKS)))
    pg.screenshot(path=OUT + r"\nms_discovery_after.png", full_page=True)
    open_group(pg, "SIMATIC monitoring settings")
    pg.screenshot(path=OUT + r"\nms_simatic_monitoring.png", full_page=True)
    print("SIMATIC monitoring:", json.dumps(pg.evaluate(CHECKS)))
    ed = pg.get_by_text("Parameter editor", exact=True).locator("xpath=ancestor::*[3]")
    print("text:", " ".join((ed.first.inner_text() if ed.count() else "").split())[:1500])
