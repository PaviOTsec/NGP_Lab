from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    top = fr.locator(".ui-dialog:visible").last
    print("closing:", " ".join(top.inner_text().split())[:30])
    top.get_by_role("button", name="Cancel").click(); op.wait_for_timeout(1500)
    picker = fr.locator(".ui-dialog:visible").last
    print("now top:", " ".join(picker.inner_text().split())[:30])
    picker.locator("select#DEVICELISTCHANGEDEVICETYPE_SETDEVICETYPE_device_family_dropdown").select_option(label="SIEMENS_SCALANCE_MSPS"); op.wait_for_timeout(2500)
    rows = picker.evaluate("d => [...d.querySelectorAll('tr[id]')].filter(r => r.offsetParent && r.id).map(r => r.id + ' :: ' + (r.innerText||'').trim().replace(/\\s+/g,' ').slice(0,90))")
    print("MSPS profiles:", rows)
