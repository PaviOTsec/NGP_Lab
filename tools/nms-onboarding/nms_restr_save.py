from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
GRID = """() => [...document.querySelectorAll('div[role=row]')].map(r =>
    [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => /PROFINET|L1L2/.test(t))"""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.locator("#sa_ocm_discoveryRestrictionDoneBtn").click(); pg.wait_for_timeout(2500)
    rows = pg.evaluate(GRID); print("list (unsaved):", rows)
    if rows:
        pg.get_by_role("button", name="OK", exact=True).last.click(); pg.wait_for_timeout(3500)
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(800)
    m = pg.locator("div.action_dropdown_rowElement"); t = m.evaluate_all("els => els.map(e => (e.innerText||'').trim())")
    m.nth(t.index("Edit discovery restriction list")).click(); pg.wait_for_timeout(3000)
    print("saved list:", pg.evaluate(GRID))
    pg.screenshot(path=OUT + r"\nms_restriction_saved.png", full_page=True)
    pg.get_by_role("button", name="Cancel").last.click()
