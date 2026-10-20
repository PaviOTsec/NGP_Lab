"""Sync Operation, verify only the SW-Ops range is enabled, start the scan, monitor job + devices."""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
OPS = BASE + "system-administration/operation-connectivity-management/operation-management"
EXPECT = {"DMZ2": "Enabled 192.168.30.30-192.168.30.30"}
RANGES = """() => Object.fromEntries([...document.querySelectorAll('div[role=row]')]
    .map(r => [r.querySelector('[col-id=firstIP]'), r.querySelector('[col-id=lastIP]'), r.querySelector('[col-id=customStatus]'), r.querySelector('[col-id=subgroupName]')])
    .filter(([f]) => f && /\\d+\\.\\d+/.test(f.innerText))
    .map(([f, l, s, n]) => [n.innerText.trim(), s.innerText.trim() + ' ' + f.innerText.trim() + '-' + l.innerText.trim()]))"""
OPROW = """() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
    .map(c => c.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean).join(' | ')).filter(t => t.includes('192.168.30.11'))[0] || ''"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    btn = pg.get_by_role("button", name="Synchronization required")
    if btn.count():
        btn.first.click(); print("sync clicked")
    for _ in range(20):
        pg.wait_for_timeout(6000)
        pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(2500)
        row = pg.evaluate(OPROW); print(time.strftime("%H:%M:%S"), "operation:", row, flush=True)
        if "Synchronization required" not in row and "progress" not in row.lower():
            break
    # safety gate: exactly the SW-Ops range enabled
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    rng = pg.evaluate(RANGES); print("ranges:", rng)
    pg.locator("#sa_ocm_ipScanRangeBaseCancelButton").click(); pg.wait_for_timeout(1500)
    enabled = {k: v for k, v in rng.items() if v.startswith("Enabled")}
    if enabled != EXPECT:
        sys.exit(f"ABORT: enabled ranges are {enabled}, expected {EXPECT}; scan NOT started")
    if "Synchronization required" in pg.evaluate(OPROW):
        sys.exit("ABORT: Operation still not synchronized; scan NOT started")
    pg.get_by_text("Start network scan", exact=True).first.click(); print(time.strftime("%H:%M:%S"), "scan started", flush=True)
    for _ in range(30):
        pg.wait_for_timeout(20000)
        pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(2500)
        row = pg.evaluate(OPROW); print(time.strftime("%H:%M:%S"), "operation:", row, flush=True)
        if "scan" not in row.lower() and "Executing" not in row:
            break
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle"); pg.wait_for_timeout(6000)
    devs = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => {
        const g = id => { const c = r.querySelector('[col-id="' + id + '"]'); return c ? c.innerText.trim().replace(/\\s+/g,' ') : ''; };
        return [g('status'), g('ip/Subnet'), g('sysName'), g('deviceType'), g('mac')].join(' | ');
      }).filter(t => t.replace(/[ |]/g,''))""")
    print("\n".join(devs))
    pg.screenshot(path=OUT + r"\nms_devices_swops.png", full_page=True)
