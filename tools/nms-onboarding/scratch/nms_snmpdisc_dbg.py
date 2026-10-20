from playwright.sync_api import sync_playwright
BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
    print(pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].filter(r => /SNMP Settings V/.test(r.innerText||''))
        .map(r => r.getAttribute('row-index') + ' ' + (r.innerText||'').trim().replace(/\\s+/g,' ') + ' cbs=' + r.querySelectorAll('input[type=checkbox]').length)"""))
    print("rows with row-index 0/1:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row][row-index]')].map(r => r.getAttribute('row-index') + ':' + r.className.slice(0,40) + ':cb=' + r.querySelectorAll('input[type=checkbox]').length + ':' + (r.innerText||'').trim().slice(0,30))"""))
    print("Disable elements:", pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e => e.children.length === 0 && (e.innerText||'').trim() === 'Disable')
        .map(e => e.tagName + '.' + (e.className||'') + ' vis=' + !!e.offsetParent + ' parent=' + (e.parentElement.className||''))"""))
