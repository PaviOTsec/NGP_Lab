import re, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://" + sys.argv[1]))
    for src in sys.argv[2:]:
        js = pg.evaluate("u => fetch(u, {credentials: 'same-origin'}).then(r => r.text())", src)
        hits = set()
        for m in re.finditer(r"(?i)(hmac|sha-?2|sha ?256|sha ?512|sha1|\bsha\b|aes ?256|aes ?128|aes|\bdes\b|md5)", js):
            hits.add(js[max(0, m.start()-90):m.end()+90].replace("\n", " "))
        snmp = [h for h in hits if re.search(r"(?i)snmp|auth|priv|v3", h)]
        print(f"== {src}: {len(js)} bytes, {len(snmp)} snmp-ish hits")
        for h in sorted(snmp)[:25]:
            print("  ", h)
