from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
TOOLBAR = """() => [...document.querySelectorAll('*')].filter(e => e.offsetParent && e.children.length === 0
     && /^(Stop|Abort|Cancel|Delete|Pause|Terminate|Stop network scan|Start network scan|Edit scan ranges|Add Operation|Synchronize Operations|Actions)/.test((e.innerText||'').trim()))
     .map(e => (e.innerText||'').trim() + (/disabled/i.test((e.closest('button,a,li,div')||e).className) ? ' (disabled)' : ''))"""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    box = pg.locator("div[role=row]:has([role=gridcell]:text-is('1008')) input[type=checkbox]")
    print("1008 checkbox:", box.count())
    if box.count() == 1:
        box.first.check(force=True); pg.wait_for_timeout(1500)
        print("jobs toolbar with 1008 selected:", pg.evaluate(TOOLBAR))
        pg.screenshot(path=OUT + r"\nms_jobs_1008_selected.png")
        box.first.uncheck(force=True)
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    acts = pg.get_by_text("Actions", exact=True)
    if acts.count():
        acts.first.click(); pg.wait_for_timeout(1500)
        print("operations Actions menu:", pg.evaluate(TOOLBAR))
        pg.screenshot(path=OUT + r"\nms_operations_actions.png")
        pg.keyboard.press("Escape")
    print("operations toolbar:", pg.evaluate(TOOLBAR))
