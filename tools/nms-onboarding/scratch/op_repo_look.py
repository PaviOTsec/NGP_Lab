from playwright.sync_api import sync_playwright
OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    print("url before:", op.url)
    op.locator("#nav_ntwrkAdmin").click(); op.wait_for_timeout(1200)
    op.locator("a[href='#/network-administration/device-credentials']").first.click(); op.wait_for_timeout(8000)
    print("url after:", op.url)
    print(op.evaluate("() => [...document.querySelectorAll('div[role=row]')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ')).filter(t => /\\d+\\.\\d+/.test(t))"))
    op.screenshot(path=OUT + r"\op_cred_repo.png", full_page=True)

