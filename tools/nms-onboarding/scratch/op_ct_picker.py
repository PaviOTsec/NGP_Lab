import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    fr.locator("#DEVICELISTCHANGEDEVICETYPE_SETDEVICETYPE_setDevice_type_changeDeviceType").click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\op_ct_type_picker.png", full_page=True)
    d = fr.locator(".ui-dialog:visible").last
    t = d.inner_text()
    print("picker title/len:", " ".join(t.split())[:200], len(t))
    print("SC6 matches:", sorted(set(re.findall(r"[^\n\t]*SC6[^\n\t]*", t)))[:20])
    print("inputs:", d.evaluate("d => [...d.querySelectorAll('input,select')].filter(e => e.offsetParent).map(e => e.tagName + ' id=' + e.id + ' ph=' + (e.placeholder||'') + ' title=' + (e.title||''))"))
