from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    links = op.eval_on_selector_all("a[href]", "els => els.map(e => (e.innerText||'').trim() + ' -> ' + e.getAttribute('href')).filter(x => /opolog/i.test(x))")
    print("topology links:", links)
    href = next((l.split(" -> ")[1] for l in links), "#/network-monitoring/opMon/topology")
    op.evaluate(f"() => {{ location.hash = '{href}'; }}"); op.wait_for_timeout(12000)
    op.screenshot(path=OUT + r"\op_topology.png", full_page=True)
    print("url:", op.url)
