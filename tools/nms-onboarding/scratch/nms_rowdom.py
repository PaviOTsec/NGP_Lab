import re
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.get_by_text("Edit scan ranges", exact=True).click()
    pg.wait_for_timeout(3000)
    el = pg.get_by_text("Supervisory", exact=True).first
    html = el.evaluate("e => { let r = e; for (let i = 0; i < 6 && r.parentElement; i++) { r = r.parentElement; if ((r.getAttribute('role')||'') === 'row' || r.tagName === 'TR') break; } return r.outerHTML; }")
    html = re.sub(r'_ngcontent-[\w-]+=""|_nghost-[\w-]+=""', '', html)
    print(html[:3500])
