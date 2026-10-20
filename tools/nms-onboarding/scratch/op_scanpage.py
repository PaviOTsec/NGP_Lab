from playwright.sync_api import sync_playwright
OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    op.evaluate("() => { location.hash = '#/network-monitoring/opMon/settings-scan'; }"); op.wait_for_timeout(6000)
    op.screenshot(path=OUT + r"\op_settings_scan.png", full_page=True)
    print("buttons:", op.evaluate("() => [...document.querySelectorAll('button, a.btn, input[type=button]')].filter(e => e.offsetParent).map(e => (e.innerText||e.value||'').trim()).filter(Boolean)"))
    t = " ".join(op.inner_text("body").split()); i = t.find("Network scan"); print("text:", t[i:i+1200])
