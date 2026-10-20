import sys, time
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OPS = BASE + "system-administration/operation-connectivity-management/operation-management"
OPROW = """() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
    .map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => t.includes('192.168.30.11'))[0] || ''"""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    print("before:", pg.evaluate(OPROW))
    btn = pg.get_by_role("button", name="Synchronization required")
    if btn.count(): btn.first.click(); print("sync clicked")
    for _ in range(30):
        pg.wait_for_timeout(8000)
        pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(2500)
        row = pg.evaluate(OPROW); print(time.strftime("%H:%M:%S"), row, flush=True)
        if "| OK |" in row and "ynchroniz" not in row:
            break
