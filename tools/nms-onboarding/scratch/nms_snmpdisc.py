import json
from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
CTRL = """() => [...document.querySelectorAll('select,input')].filter(e => e.offsetParent && e.type !== 'hidden')
    .map(e => (e.placeholder || e.name || e.id || '').slice(0,40) + '=' + (e.type === 'password' ? '(hidden)' : e.type === 'checkbox' ? e.checked : (e.tagName === 'SELECT' ? e.options[e.selectedIndex]?.text : e.value)))"""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    if pg.get_by_placeholder("User name*").count(): print("CONTROL SESSION EXPIRED"); raise SystemExit
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
    pg.screenshot(path=OUT + r"\nms_snmp_discovery_settings.png", full_page=True)
    ed = pg.get_by_text("Parameter editor", exact=True).locator("xpath=ancestor::*[3]")
    print("text:", " ".join((ed.first.inner_text() if ed.count() else "").split())[-1500:])
    print("controls:", pg.evaluate(CTRL))
    print("grid:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')]
        .map(c => (c.getAttribute('col-id')||'') + '=' + c.innerText.trim().replace(/\\s+/g,' ')).filter(x => !x.endsWith('=')).join(' | ')).filter(Boolean)"""))
