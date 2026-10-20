import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://" + sys.argv[1]))
    print(pg.url)
    html = pg.content()
    i = html.find("ConfigPack")
    print(html[max(0, i-1500):i+600])
