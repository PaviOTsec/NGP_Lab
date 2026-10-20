from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    name = pg.locator("input[placeholder='Enter name']")
    ok = pg.locator("#sa_ocm_discoveryRestrictionDoneBtn")
    for candidate in ("L1L2_noPROFINET", "L1L2noPROFINET"):
        name.click(); name.press("Control+a"); name.press("Delete")
        pg.keyboard.type(candidate, delay=30); pg.keyboard.press("Tab"); pg.wait_for_timeout(1200)
        print(candidate, "-> OK enabled:", ok.is_enabled(), "| name class:", name.get_attribute("class"))
        if ok.is_enabled():
            break
    pg.screenshot(path=OUT + r"\nms_restriction_filled2.png", full_page=True)
