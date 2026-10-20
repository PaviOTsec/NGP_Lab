from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
GRID = """() => [...document.querySelectorAll('div[role=row]')].filter(r => /SNMP Settings V/.test(r.innerText||'')).map(r => (r.innerText||'').trim().replace(/\\s+/g,' '))"""
def open_group(pg):
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front(); open_group(pg)
    btn = pg.locator("button.parameterDisableButton")
    for i in (0, 1):
        pg.locator(f"div[role=row][row-index='{i}'] .ag-selection-checkbox, div[role=row][row-index='{i}'] .ag-checkbox-input-wrapper").first.click()
        pg.wait_for_timeout(500)
    print("Disable button class now:", btn.get_attribute("class"))
    if "disabledBtn" in (btn.get_attribute("class") or ""):
        raise SystemExit("selection did not register; nothing changed")
    btn.click(); pg.wait_for_timeout(1500)
    rows = pg.evaluate(GRID); print("before save:", rows)
    if len(rows) == 2 and all(r.startswith("Disabled") for r in rows):
        pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_timeout(4000)
    else:
        raise SystemExit("unexpected state; not saved")
    open_group(pg); print("after reload:", pg.evaluate(GRID))
    pg.screenshot(path=OUT + r"\nms_snmp_discovery_disabled.png", full_page=True)
