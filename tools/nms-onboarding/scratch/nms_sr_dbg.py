from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.screenshot(path=OUT + r"\nms_sr_form_invalid.png", full_page=True)
    print(pg.evaluate("""() => [...document.querySelectorAll('input[id^=sa_ocm_scanRange], select[id^=sa_ocm_scanRange]')]
        .map(e => e.id + ' value=' + (e.type==='checkbox' ? e.checked : e.value) + ' class=' + e.className)"""))
    print("messages:", pg.evaluate("""() => [...document.querySelectorAll('[class*=error],[class*=invalid],[class*=warn],[class*=tooltip],[role=alert]')]
        .filter(e => e.offsetParent && (e.innerText||'').trim()).map(e => (e.innerText||'').trim().slice(0,150))"""))
