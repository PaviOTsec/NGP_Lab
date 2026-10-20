import re
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.goto(BASE + "system-monitoring/job-monitor/job-list", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    t = " ".join(pg.inner_text("body").split())
    print("job 1008:", re.search(r"1008 discovery.{0,160}", t).group(0) if re.search(r"1008 discovery", t) else "not found")
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle")
    pg.wait_for_timeout(5000)
    print("devices page:", " ".join(pg.inner_text("body").split())[:3000])
