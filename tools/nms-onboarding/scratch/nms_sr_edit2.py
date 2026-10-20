from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
GRID = """() => Object.fromEntries([...document.querySelectorAll('div[role=row]')]
    .map(r => [r.querySelector('[col-id=firstIP]'), r.querySelector('[col-id=lastIP]'), r.querySelector('[col-id=customStatus]'), r.querySelector('[col-id=subgroupName]')])
    .filter(([f]) => f && /\\d+\\.\\d+/.test(f.innerText))
    .map(([f, l, s, n]) => [n.innerText.trim(), s.innerText.trim() + ' ' + f.innerText.trim() + '-' + l.innerText.trim()]))"""
def typ(pg, sel, val):
    f = pg.locator(sel); f.click(); f.press("Control+a"); f.press("Delete"); pg.keyboard.type(val, delay=25); pg.keyboard.press("Tab")
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    assert pg.locator("#sa_ocm_scanRangeEditorFirstIp").input_value() == "192.168.30.1", "edit form not on DMZ2"
    typ(pg, "#sa_ocm_scanRangeEditorFirstIp", "192.168.30.30")
    typ(pg, "#sa_ocm_scanRangeEditorLastIp", "192.168.30.30")
    en = pg.locator("#sa_ocm_scanRangeEnable")
    if not en.is_checked(): en.check(force=True)
    pg.wait_for_timeout(1000)
    print("size:", pg.locator("#sa_ocm_scanRangeSize").input_value(), "OK enabled:", pg.locator("#sa_ocm_scanRangeDoneBtn").is_enabled())
    pg.locator("#sa_ocm_scanRangeDoneBtn").click(); pg.wait_for_timeout(2500)
    g = pg.evaluate(GRID); print("unsaved:", g)
    good = g.get("DMZ2") == "Enabled 192.168.30.30-192.168.30.30" and all(v.startswith("Disabled") for k, v in g.items() if k != "DMZ2")
    pg.locator("#sa_ocm_ipScanRangeBaseSaveButton" if good else "#sa_ocm_ipScanRangeBaseCancelButton").click(); pg.wait_for_timeout(4000)
    print("saved" if good else "CANCELLED (unexpected state)")
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    print("re-read:", pg.evaluate(GRID))
    pg.screenshot(path=OUT + r"\nms_scanranges_swops.png", full_page=True)
    pg.locator("#sa_ocm_ipScanRangeBaseCancelButton").click()
