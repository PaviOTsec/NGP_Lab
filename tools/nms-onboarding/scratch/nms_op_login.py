import hashlib, socket, ssl, sys, json
from pathlib import Path
sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore
from playwright.sync_api import sync_playwright
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
with c.wrap_socket(socket.create_connection(("192.168.30.11", 8443), 5)) as s:
    print("8443 cert SHA256:", hashlib.sha256(s.getpeercert(True)).hexdigest().upper())
cred = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml").credential("sinec-nms/web-portal")
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    try:
        if op.get_by_placeholder("User name*").count():
            u = op.get_by_placeholder("User name*"); u.click(); u.fill(cred.username)
            op.evaluate("() => { const e = document.getElementById('passwordtab'); if (e) e.removeAttribute('readonly'); }")
            op.get_by_placeholder("Password*").click(); op.keyboard.type(cred.password or "", delay=20)
            op.get_by_role("button", name="Log in").click(); op.wait_for_timeout(7000)
        print("url:", op.url)
        links = op.eval_on_selector_all("a[href]", "els => els.map(e => (e.innerText||'').trim() + ' -> ' + e.getAttribute('href')).filter(x => !x.startsWith(' ->'))")
        print([l for l in links if any(k in l for k in ('redential', 'Cockpit', 'Devices', 'Network scan', 'Settings'))])
        op.screenshot(path=OUT + r"\nms_operation_home.png")
    except Exception as e:
        print("failed:", type(e).__name__)
