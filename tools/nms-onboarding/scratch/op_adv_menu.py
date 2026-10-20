from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    print("selected:", fr.evaluate("() => [...document.querySelectorAll('tr.ui-state-highlight, tr[aria-selected=true]')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ').slice(0,60))"))
    fr.locator("#DEVICELIST_INIT_new_icon").click(); op.wait_for_timeout(1500)
    op.screenshot(path=OUT + r"\op_advanced_menu.png", full_page=True)
    print("menu:", fr.evaluate("""() => [...document.querySelectorAll('li, .menu-item, [role=menuitem], div[id^=DEVICELIST], a')].filter(e => { const r = e.getBoundingClientRect(); return e.offsetParent && r.y > 80 && r.y < 500 && r.x > 300 && r.x < 800; })
        .map(e => e.tagName + ' id=' + e.id + ' "' + ((e.innerText||e.getAttribute('title')||'').trim().replace(/\\s+/g,' ').slice(0,60)) + '"').filter(s => !s.endsWith('""'))"""))
