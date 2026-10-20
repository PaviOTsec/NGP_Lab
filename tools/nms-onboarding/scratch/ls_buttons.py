from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.30"))
    print(pg.evaluate("""() => [...document.querySelectorAll('input[type=button],input[type=submit],button,a[href*=".cfg"],a[href*="save"],a[href*="load"],form')]
        .map(e => e.tagName + ' ' + (e.value||e.innerText||'').trim().slice(0,30) + ' | ' + (e.getAttribute('onclick')||e.getAttribute('href')||e.getAttribute('action')||'').slice(0,160))"""))
