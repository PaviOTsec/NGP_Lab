from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    print(op.evaluate("""() => [...document.querySelectorAll('*')].filter(e => { const r = e.getBoundingClientRect(); return e.offsetParent && r.y > 222 && r.y < 245 && r.x > 260 && r.x < 345 && r.width < 40; })
        .map(e => { const r = e.getBoundingClientRect(); return e.tagName + ' @(' + Math.round(r.x) + ',' + Math.round(r.y) + ') id=' + e.id + ' title=' + (e.getAttribute('title')||'') + ' cls=' + (e.className||'').toString().slice(0,60) + ' onclick=' + (e.getAttribute('onclick')||'').slice(0,60); })"""))
