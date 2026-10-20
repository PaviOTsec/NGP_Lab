import sys
sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore
from playwright.sync_api import sync_playwright
OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    op = next((x for x in ctx.pages if x.url.startswith("https://192.168.30.11:8443")), None) or ctx.new_page()
    op.bring_to_front()
    op.goto(OPB + "home", wait_until="networkidle"); op.wait_for_timeout(3000)
    if op.get_by_placeholder("User name*").count():
        cred = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml").credential("sinec-nms/web-portal")
        u = op.get_by_placeholder("User name*"); u.click(); u.fill(cred.username)
        op.evaluate("() => { const e = document.getElementById('passwordtab'); if (e) e.removeAttribute('readonly'); }")
        op.get_by_placeholder("Password*").click(); op.keyboard.type(cred.password or "", delay=20)
        op.get_by_role("button", name="Log in").click(); op.wait_for_timeout(7000)
    op.evaluate("() => { location.hash = '#/network-monitoring/opMon/devices'; }"); op.wait_for_timeout(8000)
    for fr in op.frames:
        if "/monitoring/?" not in fr.url: continue
        print(fr.evaluate("""() => [...document.querySelectorAll('[title]')].filter(e => e.offsetParent && e.getAttribute('title').trim())
            .map(e => { const r = e.getBoundingClientRect(); return e.tagName + ' id=' + e.id + ' "' + e.getAttribute('title') + '" @(' + Math.round(r.x) + ',' + Math.round(r.y) + ')'; })
            .filter(s => / @\\(\\d+,(2[2-5]\\d)\\)/.test(s) || /delet|remove/i.test(s))"""))
