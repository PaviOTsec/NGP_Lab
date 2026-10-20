from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    form = pg.get_by_text("Create restriction", exact=True).locator("xpath=ancestor::*[.//input[@placeholder='Enter name']][1]")
    form.locator("input[placeholder='Enter name']").fill("L1-L2 no PROFINET")
    form.locator("input[placeholder='IP,IP,IP-IP,CIDR']").fill("192.168.1.0-192.168.4.255,192.168.20.0/24")
    for lbl in ("No PROFINET discovery", "Enable"):
        t = form.get_by_text(lbl, exact=True).first
        cb = t.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]//input[@type='checkbox']").first
        if not cb.is_checked(): cb.check(force=True)
        print(lbl, "checked:", cb.is_checked())
    form.locator("select").select_option(label="DMZH2Maint")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT + r"\nms_restriction_filled.png", full_page=True)
    form.get_by_role("button", name="OK", exact=True).click(); pg.wait_for_timeout(2500)
    grid = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r =>
        [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => /PROFINET|192\\.168\\.1/.test(t))""")
    print("list before OK:", grid)
    if grid:
        pg.get_by_role("button", name="OK", exact=True).last.click(); pg.wait_for_timeout(3000)
    # re-open to confirm it was saved
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(800)
    rows = pg.locator("div.action_dropdown_rowElement"); texts = rows.evaluate_all("els => els.map(e => (e.innerText||'').trim())")
    rows.nth(texts.index("Edit discovery restriction list")).click(); pg.wait_for_timeout(3000)
    print("saved list:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r =>
        [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => /PROFINET|192\\.168\\.1/.test(t))"""))
    pg.screenshot(path=OUT + r"\nms_restriction_saved.png", full_page=True)
    pg.get_by_role("button", name="Cancel").last.click()
