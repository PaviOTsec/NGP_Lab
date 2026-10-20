import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.startswith("https://" + sys.argv[1]))
    rows = pg.evaluate("""() => [...document.querySelectorAll('form[action*="loadandsave_http"] tr')].map((tr, i) => {
        const tds = [...tr.querySelectorAll('td,th')].map(td => td.innerText.trim());
        const save = tr.querySelector('input[value="Save"]');
        return i + ': ' + tds.join(' | ') + (save ? '  [save ' + (save.disabled ? 'disabled' : 'enabled') + ' name=' + (save.name||save.id) + ']' : '');
      })""")
    print("\n".join(rows))
