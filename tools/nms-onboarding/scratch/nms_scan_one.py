"""Gated single-range scan: requires Operation synced (status OK, no sync text) and exactly the
expected enabled range; starts the scan, waits for the NEW discovery job to finish, lists devices.
usage: python -I nms_scan_one.py <range-name> <first-ip> <last-ip>"""
import sys
import time
from playwright.sync_api import sync_playwright

NAME, FIRST, LAST = sys.argv[1:4]
EXPECT = {NAME: f"Enabled {FIRST}-{LAST}"}
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
OPS = BASE + "system-administration/operation-connectivity-management/operation-management"
JOBS = BASE + "system-monitoring/job-monitor/job-list"
RANGES = """() => Object.fromEntries([...document.querySelectorAll('div[role=row]')]
    .map(r => [r.querySelector('[col-id=firstIP]'), r.querySelector('[col-id=lastIP]'), r.querySelector('[col-id=customStatus]'), r.querySelector('[col-id=subgroupName]')])
    .filter(([f]) => f && /\\d+\\.\\d+/.test(f.innerText))
    .map(([f, l, s, n]) => [n.innerText.trim(), s.innerText.trim() + ' ' + f.innerText.trim() + '-' + l.innerText.trim()]))"""
OPROW = """() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
    .map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => t.includes('192.168.30.11'))[0] || ''"""
DISC = """() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')].map(c => c.innerText.trim()))
    .filter(c => c.length > 8 && c[1] === 'discovery').map(c => [c[0], c[4], c[8]])"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(JOBS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    before = {j[0] for j in pg.evaluate(DISC)}
    pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    row = pg.evaluate(OPROW)
    if "| OK |" not in row or "ynchroniz" in row:
        sys.exit(f"ABORT: Operation not idle/synced: {row}")
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    rng = pg.evaluate(RANGES)
    pg.locator("#sa_ocm_ipScanRangeBaseCancelButton").click(); pg.wait_for_timeout(1500)
    enabled = {k: v for k, v in rng.items() if v.startswith("Enabled")}
    if enabled != EXPECT:
        sys.exit(f"ABORT: enabled ranges {enabled} != {EXPECT}")
    start = pg.get_by_text("Start network scan", exact=True).first
    print("gate passed; start button class:", start.evaluate("e => (e.closest('button,div,a')||e).className"))
    start.click()
    print(time.strftime("%H:%M:%S"), "scan requested", flush=True)
    job = None
    for _ in range(40):
        pg.wait_for_timeout(15000)
        pg.goto(JOBS, wait_until="networkidle"); pg.wait_for_timeout(2500)
        new = [j for j in pg.evaluate(DISC) if j[0] not in before]
        if new:
            job = new[0]
            print(time.strftime("%H:%M:%S"), "job", job, flush=True)
            if not job[2].startswith("Executing"):
                break
        elif _ >= 3:
            sys.exit("no new discovery job appeared — scan did not start")
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(6000)
    devs = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => {
        const g = id => { const c = r.querySelector('[col-id="' + id + '"]'); return c ? c.innerText.trim().replace(/\\s+/g,' ') : ''; };
        return [g('status'), g('ip/Subnet'), g('sysName'), g('deviceType'), g('mac')].join(' | ');
      }).filter(t => t.replace(/[ |]/g,''))""")
    print("\n".join(devs))
    pg.screenshot(path=OUT + rf"\nms_devices_after_{NAME}.png", full_page=True)
