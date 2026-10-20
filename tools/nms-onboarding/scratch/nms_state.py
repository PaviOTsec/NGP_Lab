from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    
    grid = lambda: pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r =>
        [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(Boolean)""")
    print("operations:", grid())
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    print("scan ranges:", grid())
    pg.get_by_role("button", name="Cancel").last.click(); pg.wait_for_timeout(1000)
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(5000)
    print("devices:", " ".join(pg.inner_text("body").split())[:300])

