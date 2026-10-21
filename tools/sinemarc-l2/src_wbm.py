"""Drive the operator-visible Edge (CDP 127.0.0.1:9222) on the SINEMA RC Server WBM â€” READ-ONLY.

usage: python -I src_wbm.py <backend_dir> <out_dir> <action> [arg]
  actions: login          TLS pin check, log in (only form ever submitted), print nav links
           links          print nav links of the current page
           click <text>   click a menu/tab item by its exact text, print URL + links
           goto <path>    open https://10.1.20.16<path>, print visible text + form controls
The TLS cert must match the fingerprint OT-FW pins for the server (`show sinemarc`);
otherwise no credentials are sent. Exceptions print their type only (Playwright's call log
echoes typed values).
"""
import hashlib
import json
import socket
import ssl
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
ACTION = sys.argv[3]
ARG = sys.argv[4] if len(sys.argv) > 4 else ""
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = "10.1.20.16"
BASE = f"https://{HOST}"
PIN = "B2:8E:61:69:F7:92:A6:5F:50:91:60:FE:53:08:8B:70:0E:5D:A8:EF:89:8A:4B:BA:1F:6A:60:81:11:4E:B0:7B"
OUT.mkdir(parents=True, exist_ok=True)


def tls_fp() -> str:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((HOST, 443), 5)) as s:
        return ":".join(f"{b:02X}" for b in hashlib.sha256(s.getpeercert(True)).digest())


def page_for(browser):
    for ctx in browser.contexts:
        for p in ctx.pages:
            if p.url.startswith(BASE):
                return p
    return browser.contexts[0].new_page()


def dump(page, tag: str) -> None:
    tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)[:60]
    page.screenshot(path=str(OUT / f"src_{time.strftime('%H%M%S')}_{tag}.png"), full_page=True)
    ctrls = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('input,select,textarea').forEach(e => {
        if (e.type === 'hidden' || e.type === 'password') return;
        const lab = e.id ? (document.querySelector(`label[for="${e.id}"]`) || {}).innerText : '';
        let v = e.tagName === 'SELECT'
          ? [...e.selectedOptions].map(o => o.text).join('|') + '  opts=' + [...e.options].map(o => o.text).join('|')
          : (e.type === 'checkbox' || e.type === 'radio') ? String(e.checked) : e.value;
        out.push(`${e.name || e.id} [${e.type}] ${lab ? '(' + lab.trim() + ') ' : ''}= ${v}`);
      });
      return out;
    }""")
    print("URL:", page.url)
    print("---- TEXT ----\n" + page.inner_text("body")[:20000])
    print("---- CONTROLS ----\n" + "\n".join(ctrls))


def links(page) -> None:
    for t, h in page.evaluate("() => [...document.querySelectorAll('a')].map(a => [a.innerText.trim(), a.getAttribute('href')])"):
        if h and h.startswith("/") and not h.startswith("/static"):
            print(f"{h}  {t}")


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = page_for(browser)
        page.bring_to_front()
        try:
            if ACTION == "login":
                fp = tls_fp()
                if fp != PIN:
                    sys.exit(f"TLS cert {fp} != pin; no credentials sent")
                cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("sinemarc/wbm-admin")
                page.goto(f"{BASE}/wbm/login/")
                page.fill("#id_username", cred.username)
                page.fill("#id_password", cred.password)
                page.click("#id_submit")
                page.wait_for_load_state("networkidle")
                print("after login:", page.url)
                links(page)
            elif ACTION == "links":
                links(page)
            elif ACTION == "html":  # save page HTML (no navigation) for offline reading
                p = OUT / f"src_{time.strftime('%H%M%S')}_page.html"
                p.write_text(page.content(), encoding="utf-8")
                print("saved", p)
            elif ACTION == "click":  # navigation text only (menu / tab); refuses anything save-like
                if any(w in ARG.lower() for w in ("save", "delete", "apply", "create", "reset", "restart")):
                    sys.exit("refused: not a navigation item")
                page.get_by_text(ARG, exact=True).first.click()
                page.wait_for_load_state("networkidle")
                print("URL:", page.url)
                links(page)
            elif ACTION == "goto":
                page.goto(BASE + ARG)
                page.wait_for_load_state("networkidle")
                if "/login" in page.url:
                    sys.exit("session expired; run login")
                dump(page, ARG.strip("/").replace("/", "_") or "root")
        except Exception as e:  # noqa: BLE001
            sys.exit(f"error: {type(e).__name__}")


main()
