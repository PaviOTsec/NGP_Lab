import re, time
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    for i in range(12):
        pg.goto(BASE + "system-monitoring/job-monitor/job-list", wait_until="networkidle")
        pg.wait_for_timeout(3000)
        t = " ".join(pg.inner_text("body").split())
        m = re.search(r"1008 discovery.{0,120}?(Executing \(\d+/\d+\)|Success|Failed|Aborted|Cancel\w*)", t)
        status = m.group(1) if m else "?"
        print(time.strftime("%H:%M:%S"), "job 1008:", status, flush=True)
        if not status.startswith("Executing"):
            break
        time.sleep(45)
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle")
    pg.wait_for_timeout(6000)
    rows = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r =>
        [...r.querySelectorAll('[role=gridcell]')].map(c => (c.getAttribute('col-id')||'') + '=' + c.innerText.trim().replace(/\\s+/g,' ')).filter(x => !x.endsWith('=')).join(' | ')).filter(Boolean)""")
    print("\n".join(rows))
    pg.screenshot(path=r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4\nms_devices_after_scan.png", full_page=True)
