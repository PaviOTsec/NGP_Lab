from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    d = fr.locator(".ui-dialog:visible").last
    row = d.locator("tr[id='5']")
    assert "SNMPv3_sha1" in row.inner_text()
    row.click(); op.wait_for_timeout(800)
    print("highlighted:", d.evaluate("d => [...d.querySelectorAll('tr.ui-state-highlight, tr[aria-selected=true]')].map(r => (r.innerText||'').trim().slice(0,40))"))
    d.get_by_role("button", name="Save").click(); op.wait_for_timeout(2000)
    main = fr.locator(".ui-dialog:visible").last
    print("main dialog now:", main.evaluate("""d => [...d.querySelectorAll('input')].filter(e => e.offsetParent).map(e => e.id.split('_').slice(-2).join('_') + '=' + (e.type === 'checkbox' ? e.checked : e.value))"""))
    print("OK enabled:", main.evaluate("d => [...d.querySelectorAll('button')].filter(b => (b.innerText||'').trim() === 'OK').map(b => !b.disabled && !b.className.includes('disabled'))"))
    op.screenshot(path=OUT + r"\op_ct_after_snmp.png", full_page=True)
