from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
def top(fr): return fr.locator(".ui-dialog:visible").last
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    t = top(fr); t.locator("tr[id='pos_SCALANCE_SC6XX']").click(); op.wait_for_timeout(700)
    t.get_by_role("button", name="OK").click(); op.wait_for_timeout(2500)
    t = top(fr); print("now:", " ".join(t.inner_text().split())[:30])
    types = t.evaluate("d => [...d.querySelectorAll('tr[id]')].filter(r => r.offsetParent && r.id).map(r => [r.id, (r.innerText||'').trim().replace(/\\s+/g,' ')])")
    print("types:", types)
    pick = [i for i, txt in types if "SC646" in txt]
    if len(pick) != 1: raise SystemExit("SC646 type not uniquely found; nothing chosen")
    t.locator(f"tr[id='{pick[0]}']").click(); op.wait_for_timeout(700)
    t.get_by_role("button", name="OK").click(); op.wait_for_timeout(2500)
    main = top(fr); print("main:", " ".join(main.inner_text().split())[:40])
    vals = main.evaluate("d => Object.fromEntries([...d.querySelectorAll('input')].filter(e => e.offsetParent).map(e => [e.id.split('_').slice(-2).join('_'), e.type === 'checkbox' ? e.checked : e.value]))")
    print("main values:", vals)
    okb = main.get_by_role("button", name="OK"); en = okb.evaluate("b => !b.disabled && !b.className.includes('disabled')")
    op.screenshot(path=OUT + r"\op_ct_before_ok2.png", full_page=True)
    if en and "SC6" in str(vals.get("type_textField", "")) and vals.get("setSNMPSettings_textField") == "SNMPv3_sha1":
        okb.click(); op.wait_for_timeout(4000); print("APPLIED")
        op.screenshot(path=OUT + r"\op_ct_after_ok2.png", full_page=True)
    else:
        print("not as expected (OK enabled=%s) -> nothing applied" % en)
