import re, time
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    dlg = fr.locator(".ui-dialog:visible, [role=dialog]:visible").filter(has_text="automatic device type change")
    print("dialog found:", dlg.count())
    dlg.first.get_by_role("button", name="OK").click(); op.wait_for_timeout(4000)
    op.screenshot(path=OUT + r"\op_after_autotype_ok.png", full_page=True)
    t = " ".join(fr.inner_text("body").split())
    print("follow-up:", re.findall(r"(?i)[^.]{0,150}(device type|started|enabled|change)[^.]{0,150}", t)[:4])
    print("buttons now:", fr.evaluate("() => [...document.querySelectorAll('button')].filter(e => e.offsetParent).map(e => (e.innerText||'').trim()).filter(Boolean)"))
