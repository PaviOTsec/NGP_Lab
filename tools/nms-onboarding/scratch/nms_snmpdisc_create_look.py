from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    ok = pg.get_by_role("button", name="OK", exact=True)
    if ok.count(): ok.last.click(); pg.wait_for_timeout(1000)
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
    pg.locator("text=Create").nth(1).click(); pg.wait_for_timeout(2500)   # nth(0) is the parameter-profile Create
    pg.screenshot(path=OUT + r"\nms_snmpdisc_create.png", full_page=True)
    print(pg.evaluate("""() => [...document.querySelectorAll('input,select,button')].filter(e => e.offsetParent)
        .map(e => e.tagName + ':' + (e.id||'') + ':' + (e.type||'') + ':' + (e.placeholder||(e.innerText||'').trim()||'').slice(0,45)
        + (e.tagName === 'SELECT' ? ' [' + [...e.options].map(o => o.text.trim()).join('/') + ']=' + (e.options[e.selectedIndex]||{}).text : '')).slice(-22)"""))
