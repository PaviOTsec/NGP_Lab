import re, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://" + sys.argv[1]))
    html = pg.content()
    scripts = pg.evaluate("() => [...document.scripts].map(s => s.src).filter(Boolean)")
    print("scripts:", scripts[:20])
    for m in sorted(set(re.findall(r"[^<>\"']{0,60}(?:SHA|AES|DES|MD5)[^<>\"']{0,60}", html, re.I)))[:60]:
        print("  ", m.strip())
