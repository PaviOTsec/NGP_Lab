from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    d = fr.locator(".ui-dialog:visible").last
    d.locator("select#DEVICELISTCHANGEDEVICETYPE_SETDEVICETYPE_device_family_dropdown").select_option(label="SIEMENS_SCALANCE_S600"); op.wait_for_timeout(2500)
    print(d.evaluate("d => [...d.querySelectorAll('tr[id]')].filter(r => r.offsetParent && r.id).map(r => r.id + ' :: ' + (r.innerText||'').trim().replace(/\\s+/g,' ').slice(0,100))"))
