import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    print("page:", op.url)
    target = None
    for fr in op.frames:
        try:
            n = fr.locator("#NSC_DIV_AUTO_DEVICE_TYPE_CHANGE").count()
        except Exception:
            n = 0
        print("frame", fr.url[:100], "button count:", n)
        if n and target is None: target = fr
    if not target:
        raise SystemExit("button not found in any frame")
    btn = target.locator("#NSC_DIV_AUTO_DEVICE_TYPE_CHANGE")
    print("button class/enabled:", btn.get_attribute("class"), btn.is_visible())
    btn.click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\op_after_autotype_click.png", full_page=True)
    for fr in op.frames:
        try: t = " ".join(fr.inner_text("body").split())
        except Exception: continue
        hits = re.findall(r"(?i)[^.]{0,150}(device type|confirm|are you sure|yes|started|change)[^.]{0,150}", t)
        if hits: print("TEXT", fr.url[:50], hits[:5])
    print("dialog buttons:", [ (fr.url[:40], fr.evaluate("() => [...document.querySelectorAll('button, .ui-button, input[type=button]')].filter(e => e.offsetParent).map(e => (e.innerText||e.value||'').trim()).filter(Boolean)")) for fr in op.frames if fr.url.startswith('https')])
