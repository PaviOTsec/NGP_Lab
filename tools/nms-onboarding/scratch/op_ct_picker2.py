from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    d = fr.locator(".ui-dialog:visible").last
    print(" | ".join(x.strip() for x in d.inner_text().split("\n") if x.strip())[:1500])
    print("families:", d.locator("select#DEVICELISTCHANGEDEVICETYPE_SETDEVICETYPE_device_family_dropdown").evaluate("s => [...s.options].map(o => o.text)"))
