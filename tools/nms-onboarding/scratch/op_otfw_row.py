from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    print("OT-FW row:", fr.evaluate("() => [...document.querySelectorAll('tr')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ')).filter(t => t.includes('192.168.20.254')).slice(0,2)"))
    print("events:", fr.evaluate("() => [...document.querySelectorAll('tr')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ')).filter(t => /Reread|read|20\\.254/i.test(t) && t.length < 250).slice(0,6)"))
