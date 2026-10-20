from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    for fr in op.frames:
        if "/monitoring/?" not in fr.url: continue
        print(fr.evaluate("""() => [...document.querySelectorAll('div,span,img,a,td')].filter(e => { const r = e.getBoundingClientRect(); return e.offsetParent && r.y > 30 && r.y < 90 && r.x > 240 && r.width < 40 && r.height < 40; })
            .map(e => { const r = e.getBoundingClientRect(); return e.tagName + ' id=' + e.id + ' title="' + (e.getAttribute('title')||'') + '" cls=' + (e.className||'').toString().slice(0,50) + ' @(' + Math.round(r.x) + ',' + Math.round(r.y) + ')'; })"""))
