from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(6000)
    idx = pg.evaluate("""() => { const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('192.168.20.254')); return r ? r.getAttribute('row-index') : null; }""")
    print("OT-FW row-index:", idx)
    pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(800)
    print("selected rows:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row][row-index]')].filter(r => r.querySelector('input[type=checkbox]:checked')).map(r => r.getAttribute('row-index'))"""))
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(1200)
    print("actions:", pg.locator("div.action_dropdown_rowElement").evaluate_all("els => els.map(e => (e.innerText||'').trim() + ((e.className||'').includes('disable') ? ' (disabled)' : ''))"))
    pg.screenshot(path=OUT + r"\ctl_devices_actions.png", full_page=True)
    pg.keyboard.press("Escape")
