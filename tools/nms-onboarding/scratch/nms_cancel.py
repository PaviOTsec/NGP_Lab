from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    pg.get_by_role("button", name="Cancel").last.click()
    pg.wait_for_timeout(1500)
    print("scan-range dialog still open:", pg.get_by_text("Scan ranges (", exact=False).count() > 0)
