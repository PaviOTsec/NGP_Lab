from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    dlg = fr.locator(".ui-dialog:visible").last
    print("dialog controls:", dlg.evaluate("""d => [...d.querySelectorAll('input,select,button,a,img,span[title],div[title]')].filter(e => e.offsetParent)
        .map(e => e.tagName + ' id=' + e.id + ' title=' + (e.getAttribute('title')||'') + ' val=' + (e.value||'').slice(0,40) + ' cls=' + (e.className||'').toString().slice(0,40))"""))
