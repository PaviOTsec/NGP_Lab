from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next(x for x in ctx.pages if x.url.startswith("https://192.168.30.11"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-connectivity-management/operation-management", wait_until="networkidle"); pg.wait_for_timeout(3000)
    link = pg.locator("div[role=row][row-index='1'] [role=gridcell]").filter(has_text="DMZH2Maint").first
    print("cell html:", link.evaluate("e => e.innerHTML.replace(/_ng[\\w-]+=\"\"/g,'').slice(0,300)"))
    before = len(ctx.pages)
    link.locator("a, span, div").filter(has_text="DMZH2Maint").last.click(); pg.wait_for_timeout(8000)
    print("pages:", [x.url for x in ctx.pages])
    op = ctx.pages[-1]; op.bring_to_front(); op.wait_for_timeout(2000)
    op.screenshot(path=OUT + r"\nms_operation_ui.png")
    print("title/text:", op.title(), " ".join(op.inner_text("body").split())[:300])
