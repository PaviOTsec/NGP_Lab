import re
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    fr = next(f for f in op.frames if "/monitoring/?" in f.url)
    cell = fr.locator("td[title='192.168.20.254']").first
    cell.click(); op.wait_for_timeout(1000)
    sel = fr.evaluate("() => [...document.querySelectorAll('tr.ui-state-highlight, tr[aria-selected=true]')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ').slice(0,80))")
    print("selected:", sel)
    if len(sel) != 1 or "192.168.20.254" not in sel[0]:
        raise SystemExit("selection is not exactly OT-FW; nothing clicked")
    fr.locator("#DEVICELIST_INIT_Reread_data").click(); op.wait_for_timeout(3000)
    op.screenshot(path=OUT + r"\op_reread.png", full_page=True)
    print("dialog buttons:", fr.evaluate("() => [...document.querySelectorAll('button')].filter(e => e.offsetParent).map(e => (e.innerText||'').trim()).filter(Boolean)"))
    t = " ".join(fr.inner_text("body").split())
    print("text:", re.findall(r"(?i)[^.]{0,120}(reread|re-read|read out|confirm)[^.]{0,120}", t)[:3])
