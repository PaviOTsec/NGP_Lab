from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    sel = fr.evaluate("() => [...document.querySelectorAll('tr.ui-state-highlight, tr[aria-selected=true]')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ').slice(0,60))")
    print("selected:", sel)
    if len(sel) != 1 or "192.168.20.254" not in sel[0]: raise SystemExit("not exactly OT-FW selected")
    fr.locator("#DEVICELIST_INIT_changeDeviceType:visible").first.click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\op_change_type_dialog.png", full_page=True)
    print("dialog:", fr.evaluate("""() => { const d = [...document.querySelectorAll('.ui-dialog')].filter(e => e.offsetParent).pop(); return d ? (d.innerText||'').trim().replace(/\\s+/g,' ').slice(0,1500) : 'no dialog'; }"""))
    print("selects:", fr.evaluate("""() => [...document.querySelectorAll('.ui-dialog select')].filter(e => e.offsetParent).map(s => [...s.options].map(o => o.text.trim()).filter(t => /SC6|S6|SCALANCE S|DEFAULT/i.test(t)).slice(0,20))"""))

