from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    rects = pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e => e.offsetParent && (e.innerText||'').trim() === 'Create' && e.children.length <= 2)
        .map(e => { const r = e.getBoundingClientRect(); return [e.tagName, Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)]; })""")
    print("Create candidates:", rects)
    x, y = next((cx, cy) for t, cx, cy in rects if cx > 700)
    pg.mouse.click(x, y); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT + r"\nms_snmpdisc_create.png", full_page=True)
    print(pg.evaluate("""() => [...document.querySelectorAll('input,select,button')].filter(e => e.offsetParent)
        .map(e => e.tagName + ':' + (e.id||'') + ':' + (e.type||'') + ':' + (e.placeholder||(e.innerText||'').trim()||'').slice(0,45)
        + (e.tagName === 'SELECT' ? ' [' + [...e.options].map(o => o.text.trim()).join('/') + ']=' + (e.options[e.selectedIndex]||{}).text : '')).slice(-22)"""))
