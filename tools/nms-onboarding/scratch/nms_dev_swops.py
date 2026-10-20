from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(6000)
    print("NMS:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
        .map(c => (c.getAttribute('col-id')||'') + '=' + c.innerText.trim().replace(/\\s+/g,' ')).filter(x => !x.endsWith('=')).join(' | ')).filter(t => t.includes('192.168.30.30'))"""))
