"""Operation UI: open Network monitoring > Topology (read-only) in the visible Edge and screenshot it.
TLS cert of :8443 checked against the NMS pin before any login.
usage: python -I op_topo_read.py <out_dir>"""
import hashlib
import socket
import ssl
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore  # noqa: E402

HOST = "192.168.30.11"
PIN = "4F32B17B125081DA944C7620EF2B11ADBBBAE4C553B84630131206C697491883"  # same cert on 443 and 8443
OPB = f"https://{HOST}:8443/sinecnmsWebappControl/UI/#/"
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)

c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
with c.wrap_socket(socket.create_connection((HOST, 8443), 5)) as s:
    fp = hashlib.sha256(s.getpeercert(True)).hexdigest().upper()
if fp != PIN:
    sys.exit(f"8443 TLS cert {fp} != pin; not sending credentials")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if x.url.startswith(f"https://{HOST}:8443")), None) or ctx.new_page()
    pg.bring_to_front()
    try:
        pg.goto(OPB + "home", wait_until="domcontentloaded", timeout=90000); pg.wait_for_timeout(8000)
        if pg.get_by_placeholder("User name*").count():
            cred = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml").credential("sinec-nms/web-portal")
            u = pg.get_by_placeholder("User name*"); u.click(); u.fill(cred.username)
            pg.evaluate("() => { const e = document.getElementById('passwordtab'); if (e) e.removeAttribute('readonly'); }")
            pg.get_by_placeholder("Password*").click(); pg.keyboard.type(cred.password or "", delay=20)
            pg.get_by_role("button", name="Log in").click(); pg.wait_for_timeout(7000)
        links = pg.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href')).filter(h => /opolog/i.test(h))")
        href = links[0] if links else "#/network-monitoring/opMon/topology"
        pg.evaluate(f"() => {{ location.hash = '{href.lstrip('#') if href.startswith('#') else href}'; }}")
        pg.wait_for_timeout(15000)
        pg.screenshot(path=str(OUT / "op_topology_read.png"))
        print("url:", pg.url)
        print("text:", " ".join(pg.inner_text("body").split())[:1500])
    except Exception as e:  # noqa: BLE001
        print("failed:", type(e).__name__)
