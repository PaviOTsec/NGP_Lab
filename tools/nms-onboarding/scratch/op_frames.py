from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    for f in op.frames:
        try:
            items = f.evaluate("""() => [...document.querySelectorAll('[title]')].filter(e => e.offsetParent).map(e => e.tagName + ':' + (e.id||'') + ':' + e.getAttribute('title')).slice(0, 40)""")
        except Exception as e:
            items = [type(e).__name__]
        print("FRAME", f.url[:90], "->", items)
