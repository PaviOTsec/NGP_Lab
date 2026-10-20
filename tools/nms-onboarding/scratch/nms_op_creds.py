import json
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    op.goto(OPB + "network-administration/device-credentials", wait_until="networkidle"); op.wait_for_timeout(5000)
    rows = op.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
        .map(c => (c.getAttribute('col-id')||'') + '=' + c.innerText.trim().replace(/\\s+/g,' ')).filter(x => !x.endsWith('=')).join(' | ')).filter(Boolean)""")
    print("\n".join(rows))
    op.screenshot(path=OUT + r"\nms_device_credentials.png", full_page=True)
    print("text:", " ".join(op.inner_text("body").split())[:1500])
