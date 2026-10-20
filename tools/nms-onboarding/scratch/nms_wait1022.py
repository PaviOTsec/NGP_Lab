import time
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    for _ in range(30):
        pg.goto(BASE + "system-monitoring/job-monitor/job-list", wait_until="networkidle"); pg.wait_for_timeout(3000)
        row = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim())).find(c => c[0] === '1022')""")
        st = row[8] if row else "?"; print(time.strftime("%H:%M:%S"), "1022:", st, flush=True)
        if not st.startswith("Executing"): break
        time.sleep(15)
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(6000)
    print("\n".join(pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => {
        const g = id => { const c = r.querySelector('[col-id="' + id + '"]'); return c ? c.innerText.trim().replace(/\\s+/g,' ') : ''; };
        return [g('status'), g('ip/Subnet'), g('deviceType'), g('mac')].join(' | '); }).filter(t => t.replace(/[ |]/g,''))""")))
