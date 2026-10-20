from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    for f in op.frames:
        if "monitoring/" not in f.url: continue
        print("frame url:", f.evaluate("() => location.href")[:120])
        print(f.evaluate("""() => [...document.querySelectorAll('[title], img[alt], [class*=btn], [class*=button], [class*=icon]')].filter(e => e.offsetParent)
            .map(e => { const r = e.getBoundingClientRect(); return e.tagName + ' id=' + (e.id||'') + ' title=' + (e.getAttribute('title')||e.getAttribute('alt')||'') + ' @(' + Math.round(r.x) + ',' + Math.round(r.y) + ')'; })
            .filter(s => /scan|profil|search|start|stop/i.test(s) || / @\\(\\d+,(2[0-9]|3[0-9]|[5-9])\\)/.test(s)).slice(0, 40)"""))
