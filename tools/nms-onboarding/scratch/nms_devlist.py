from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.goto(BASE + "network-monitoring/device", wait_until="networkidle")
    pg.wait_for_timeout(6000)
    rows = pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => {
        const g = id => { const c = r.querySelector('[col-id="' + id + '"]'); return c ? c.innerText.trim().replace(/\\s+/g,' ') : ''; };
        return [g('status'), g('ip/Subnet'), g('sysName'), g('deviceType'), g('mac')].join(' | ');
      }).filter(t => t.replace(/[ |]/g,''))""")
    print(len(rows), "rows"); print("\n".join(rows))
    pg.screenshot(path=OUT + r"\nms_devices_after_stop.png", full_page=True)
