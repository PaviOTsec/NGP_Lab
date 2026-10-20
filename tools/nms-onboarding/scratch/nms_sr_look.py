from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    pg.get_by_text("Create", exact=True).last.click(); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT + r"\nms_scanrange_create.png", full_page=True)
    print("fields:", pg.evaluate("""() => [...document.querySelectorAll('input,select,button')].filter(e => e.offsetParent)
        .map(e => e.tagName + ':' + (e.id||'') + ':' + (e.type||'') + ':' + (e.placeholder||(e.innerText||'').trim()||'').slice(0,40)
        + (e.tagName === 'SELECT' ? ' [' + [...e.options].map(o => o.text.trim()).join('/') + ']' : '')).slice(-14)"""))
    print("tail:", " ".join(pg.inner_text("body").split())[-500:])
