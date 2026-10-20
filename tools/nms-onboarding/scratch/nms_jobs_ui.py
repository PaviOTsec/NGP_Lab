from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-monitoring/job-monitor/job-list", wait_until="networkidle")
    pg.wait_for_timeout(4000)
    pg.screenshot(path=OUT + r"\nms_jobs.png", full_page=True)
    print(pg.evaluate("""() => [...document.querySelectorAll('button, a, [role=button], .ix-button, span.action, li')]
        .filter(e => e.offsetParent && (e.innerText||'').trim() && (e.innerText||'').trim().length < 40)
        .map(e => e.tagName + ':' + (e.innerText||'').trim().replace(/\\s+/g,' ') + (e.disabled || e.getAttribute('aria-disabled')==='true' || /disabled/.test(e.className) ? ' (disabled)' : ''))"""))
