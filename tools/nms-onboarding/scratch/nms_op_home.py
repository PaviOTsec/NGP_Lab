from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next(x for x in ctx.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    box = pg.locator("div[role=row]:has([role=gridcell]:has-text('192.168.30.11')) input[type=checkbox]")
    print("op row checkboxes:", box.count())
    if box.count(): box.last.check(force=True); pg.wait_for_timeout(800)
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(800)
    m = pg.locator("div.action_dropdown_rowElement"); t = m.evaluate_all("els => els.map(e => (e.innerText||'').trim())")
    n_before = len(ctx.pages)
    m.nth(t.index("Go to Op > Home")).click(); pg.wait_for_timeout(6000)
    op = ctx.pages[-1] if len(ctx.pages) > n_before else pg
    op.wait_for_load_state("networkidle"); op.wait_for_timeout(3000)
    print("operation UI url:", op.url)
    links = op.eval_on_selector_all("a[href]", "els => els.map(e => (e.innerText||'').trim() + ' -> ' + e.getAttribute('href')).filter(x => !x.startsWith(' ->'))")
    print([l for l in links if 'redential' in l or 'Cockpit' in l or 'Devices' in l or 'scan' in l.lower()])
    op.screenshot(path=OUT + r"\nms_operation_home.png")
