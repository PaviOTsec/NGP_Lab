from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://192.168.30.11"))
    for ip in ("192.168.20.1", "192.168.1.1"):
        cells = pg.locator(f"[col-id=firstIP]:text-is('{ip}')")
        rows = pg.locator("div[role=row]").filter(has=cells)
        rows2 = pg.locator(f"div[role=row]:has([col-id=firstIP] span:text-is('{ip}'))")
        print(ip, "cells", cells.count(), "rows(filter)", rows.count(), "rows(css has)", rows2.count(),
              "checkbox in rows2", pg.locator(f"div[role=row]:has([col-id=firstIP] span:text-is('{ip}')) [col-id=action] input[type=checkbox]").count())
