import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    rows = pg.locator("div.action_dropdown_rowElement")
    texts = rows.evaluate_all("els => els.map(e => (e.innerText||'').trim())")
    print("menu rows:", texts)
    idx = [i for i, t in enumerate(texts) if t == "Stop network scan"]
    if len(idx) == 1:
        rows.nth(idx[0]).click(); pg.wait_for_timeout(3000)
        pg.screenshot(path=OUT + r"\nms_after_stop_click.png")
        body = " ".join(pg.inner_text("body").split())
        print("after:", re.findall(r"(?i)[^.]{0,100}(stop|confirm|are you sure)[^.]{0,100}", body)[:5])
    else:
        print("not exactly one match; nothing clicked")
