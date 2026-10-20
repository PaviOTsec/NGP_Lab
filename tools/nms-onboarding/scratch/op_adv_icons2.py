from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    print("\n".join(fr.evaluate("""() => [...document.querySelectorAll('*')].filter(e => { const r = e.getBoundingClientRect(); return e.offsetParent && r.y > 30 && r.y < 60 && r.x > 480 && r.x < 760 && r.width < 40; })
        .map(e => { const r = e.getBoundingClientRect(); return '@x=' + Math.round(r.x) + ' ' + e.tagName + ' id=' + e.id + ' title="' + (e.getAttribute('title')||'') + '"'; })""")))

