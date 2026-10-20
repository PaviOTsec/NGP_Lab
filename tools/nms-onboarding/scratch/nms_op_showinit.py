import json
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
CTRL = """() => [...document.querySelectorAll('select,input')].filter(e => e.offsetParent && e.type !== 'hidden' && e.type !== 'checkbox')
    .map(e => (e.placeholder || e.name || e.id || '').slice(0,40) + '=' + (e.type === 'password' ? '(hidden)' : (e.tagName === 'SELECT' ? e.options[e.selectedIndex]?.text : e.value)))"""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    op.get_by_text("Show initial credentials", exact=True).first.click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\nms_op_initial_creds.png", full_page=True)
    print("snmp monitoring:", op.evaluate(CTRL))
    for tab in ("SNMP configuration",):
        t = op.get_by_text(tab, exact=True)
        if t.count(): t.first.click(); op.wait_for_timeout(1500); print(tab + ":", op.evaluate(CTRL))
    for n in ("Close", "Cancel", "OK"):
        btn = op.get_by_role("button", name=n, exact=True)
        if btn.count(): btn.last.click(); break
