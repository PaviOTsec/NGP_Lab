import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    item = pg.locator("div.action_dropdown_rowElement").filter(has_text=re.compile(r"^\s*Stop network scan\s*$"))
    print("matches:", item.count())
    if item.count() == 1:
        item.first.click(); pg.wait_for_timeout(3000)
        pg.screenshot(path=OUT + r"\nms_after_stop_click.png")
        body = " ".join(pg.inner_text("body").split())
        print("after:", re.findall(r"(?i)[^.]{0,100}(stop|confirm|are you sure|yes)[^.]{0,100}", body)[:5])
