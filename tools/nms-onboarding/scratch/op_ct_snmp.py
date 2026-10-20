from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    fr.locator("#DEVICELISTCHANGEDEVICETYPE_SETDEVICETYPE_setDevice_type_setSNMPSettings").click(); op.wait_for_timeout(2500)
    op.screenshot(path=OUT + r"\op_ct_snmp_select.png", full_page=True)
    d = fr.locator(".ui-dialog:visible").last
    print("top dialog:", " ".join(d.inner_text().split())[:800])
    print("controls:", d.evaluate("""d => [...d.querySelectorAll('input,select,button,tr,li')].filter(e => e.offsetParent)
        .map(e => e.tagName + ' id=' + e.id + ' ' + ((e.innerText||e.value||'').trim().replace(/\\s+/g,' ').slice(0,60)) + (e.type === 'radio' || e.type === 'checkbox' ? ' checked=' + e.checked : ''))"""))
