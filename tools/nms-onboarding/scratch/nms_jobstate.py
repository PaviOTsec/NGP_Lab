from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.goto(BASE + "system-monitoring/job-monitor/job-list", wait_until="networkidle"); pg.wait_for_timeout(3500)
    for r in pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim()))
        .filter(c => c.length > 8 && /discovery|sync/.test(c[1]))"""):
        print("job:", r[0], r[1], r[4], "|", r[8], "| next", r[9])
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    print("operation:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
        .map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => t.includes('192.168.30.11'))"""))
