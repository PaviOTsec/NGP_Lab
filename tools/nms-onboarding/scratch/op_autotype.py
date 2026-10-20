import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    f = next(fr for fr in op.frames if "/monitoring/?" in fr.url)
    f.locator("#NSC_DIV_AUTO_DEVICE_TYPE_CHANGE").click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\op_auto_type_change.png", full_page=True)
    for fr in op.frames:
        try:
            t = " ".join(fr.inner_text("body").split())
        except Exception:
            continue
        hits = re.findall(r"(?i)[^.]{0,120}(device type change|confirm|are you sure|started|profile)[^.]{0,120}", t)
        if hits: print(fr.url[:60], hits[:4])

