from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next(x for x in ctx.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    idx = pg.evaluate("""() => { const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('DMZH2Maint / 192.168.30.11')); return r ? r.getAttribute('row-index') : null; }""")
    print("row-index:", idx)
    cb = pg.locator(f"div[role=row][row-index='{idx}'] input[type=checkbox]")
    print("checkboxes for row:", cb.count())
    cb.first.check(force=True); pg.wait_for_timeout(1000)
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(800)
    m = pg.locator("div.action_dropdown_rowElement"); t = m.evaluate_all("els => els.map(e => (e.innerText||'').trim() + ((e.className||'').includes('disable') ? ' (disabled)' : ''))")
    print("menu:", t)
    n_before = len(ctx.pages)
    m.nth([x.split(' (')[0] for x in t].index("Go to Op > Home")).click(); pg.wait_for_timeout(8000)
    op = ctx.pages[-1]
    op.bring_to_front(); op.wait_for_timeout(3000)
    print("pages:", [x.url for x in ctx.pages])
    op.screenshot(path=OUT + r"\nms_operation_home.png")
