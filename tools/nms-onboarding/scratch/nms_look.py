"""Read-only look at SINEC NMS Control: log in, screenshot, list navigation. Clicks nothing
that changes state. usage: python -I nms_look.py <backend_dir> <out_dir>"""
import hashlib
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = "192.168.30.11"
ctx_ssl = ssl.create_default_context()
ctx_ssl.check_hostname = False
ctx_ssl.verify_mode = ssl.CERT_NONE
with ctx_ssl.wrap_socket(socket.create_connection((HOST, 443), 5)) as s:
    print("NMS TLS cert SHA256:", hashlib.sha256(s.getpeercert(True)).hexdigest().upper())

cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("sinec-nms/web-portal")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 1000}).new_page()
    page.goto(f"https://{HOST}/sinecnmsWebappControl/UI/#/login", wait_until="networkidle", timeout=60000)
    try:  # never let Playwright's call log (which echoes typed values) reach the output
        user = page.get_by_placeholder("User name*")
        user.click()
        user.fill(cred.username)
        pw = page.get_by_placeholder("Password*")
        # The field is readonly as an anti-autofill measure; lift it, then type real keys.
        page.evaluate("() => document.getElementById('passwordtab').removeAttribute('readonly')")
        pw.click()
        page.keyboard.type(cred.password or "", delay=20)
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Log in").click()
    except Exception as e:  # noqa: BLE001
        print("login step failed:", type(e).__name__)
        page.screenshot(path=str(OUT / "nms_login_failed.png"))
        sys.exit(1)
    page.wait_for_timeout(8000)
    page.wait_for_load_state("networkidle", timeout=60000)
    print("url after login:", page.url)
    page.screenshot(path=str(OUT / "nms_home.png"))
    body = " ".join(page.inner_text("body").split())
    print("text:", body[:1500])
    base = f"https://{HOST}/sinecnmsWebappControl/UI/#/"
    for slug in ["system-administration/control-administration/system-information",
                 "system-administration/operation-connectivity-management/operation-management",
                 "system-administration/operation-system-settings"]:
        page.goto(base + slug, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)
        fname = slug.rsplit("/", 1)[-1]
        page.screenshot(path=str(OUT / f"nms_{fname}.png"), full_page=True)
        print(f"\n[{fname}]", " ".join(page.inner_text("body").split())[:2500])
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => (e.innerText||'').trim() + ' -> ' + e.getAttribute('href'))")
    print("links:", [l for l in links if l.strip(" ->")][:80])
    browser.close()
