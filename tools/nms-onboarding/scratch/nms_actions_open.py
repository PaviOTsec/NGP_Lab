from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.get_by_text("Actions", exact=True).first.click(); pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT + r"\nms_actions_open.png")
    print(pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e => (e.innerText||'').trim() === 'Stop network scan')
        .map(e => e.tagName + '.' + e.className + ' vis=' + !!e.offsetParent + ' rect=' + JSON.stringify(e.getBoundingClientRect()))"""))
