from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    picker = fr.locator(".ui-dialog:visible").last
    picker.locator("tr[id='pos_SCALANCE_S']").click(); op.wait_for_timeout(700)
    picker.get_by_role("button", name="OK").click(); op.wait_for_timeout(2000)
    main = fr.locator(".ui-dialog:visible").last
    vals = main.evaluate("d => Object.fromEntries([...d.querySelectorAll('input')].filter(e => e.offsetParent).map(e => [e.id.split('_').slice(-2).join('_'), e.type === 'checkbox' ? e.checked : e.value]))")
    print("main dialog:", vals)
    okbtn = main.get_by_role("button", name="OK")
    enabled = okbtn.evaluate("b => !b.disabled && !b.className.includes('disabled')")
    print("OK enabled:", enabled)
    op.screenshot(path=OUT + r"\op_ct_before_ok.png", full_page=True)
    if enabled and vals.get("type_textField") == "SCALANCE_S" and vals.get("setSNMPSettings_textField") == "SNMPv3_sha1":
        okbtn.click(); op.wait_for_timeout(4000); print("applied")
        op.screenshot(path=OUT + r"\op_ct_after_ok.png", full_page=True)
    else:
        print("not as expected -> left open, nothing applied")
