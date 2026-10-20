import json
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    # select the Operation row (restriction list is per Operation), then Actions > Edit discovery restriction list
    box = pg.locator("div[role=row]:has([role=gridcell]:text-is('DMZH2Maint / 192.168.30.11')) input[type=checkbox]")
    print("operation checkbox:", box.count())
    if box.count() == 1: box.first.check(force=True); pg.wait_for_timeout(800)
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(1000)
    rows = pg.locator("div.action_dropdown_rowElement")
    texts = rows.evaluate_all("els => els.map(e => (e.innerText||'').trim())")
    i = texts.index("Edit discovery restriction list")
    rows.nth(i).click(); pg.wait_for_timeout(3000)
    pg.screenshot(path=OUT + r"\nms_restriction_dialog.png", full_page=True)
    print("dialog:", " ".join(pg.inner_text("body").split())[-1500:])
    print("inputs:", pg.evaluate("""() => [...document.querySelectorAll('input,select,textarea,button')].filter(e => e.offsetParent)
        .map(e => e.tagName + ':' + (e.type||'') + ':' + (e.placeholder||e.name||(e.innerText||'').trim()||e.value||'').slice(0,40))"""))
