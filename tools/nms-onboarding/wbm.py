"""Drive the operator-visible Edge (CDP 127.0.0.1:9222) — SCALANCE WBM, READ-ONLY.

usage: python -I wbm.py <backend_dir> <out_dir> <ip> <action> [arg]
  actions: login            log in, print menu links
           goto <frag>      open a WBM page whose link text/href contains <frag>, print
                            form controls (select options) and visible text
Nothing is ever submitted except the login form. Exceptions print their type only
(Playwright's call log echoes typed values).
"""
import hashlib
import json
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
IP, ACTION = sys.argv[3], sys.argv[4]
ARG = sys.argv[5] if len(sys.argv) > 5 else ""
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUT.mkdir(parents=True, exist_ok=True)
PINS = OUT / "tls_pins.json"


def tls_fp(host: str) -> str:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((host, 443), 5)) as s:
        return "SHA256:" + hashlib.sha256(s.getpeercert(True)).hexdigest().upper()


def check_pin(host: str) -> None:
    pins = json.loads(PINS.read_text()) if PINS.exists() else {}
    fp = tls_fp(host)
    if host in pins and pins[host] != fp:
        sys.exit(f"TLS cert for {host} changed ({fp} != {pins[host]}); not sending credentials")
    if host not in pins:
        pins[host] = fp
        PINS.write_text(json.dumps(pins, indent=1))
        print(f"first contact: pinned {host} {fp}")


def find_page(browser, ip):
    for ctx in browser.contexts:
        for p in ctx.pages:
            if p.url.startswith(f"https://{ip}"):
                return p
    return None


def dump(page, tag):
    page.screenshot(path=str(OUT / f"{IP}_{tag}.png"), full_page=True)
    ctrls = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('select').forEach(s => out.push({select: s.name || s.id,
         options: [...s.options].map(o => o.text.trim())}));
      return out; }""")
    for f in page.frames:
        if f != page.main_frame:
            try:
                ctrls += f.evaluate("""() => [...document.querySelectorAll('select')].map(s =>
                    ({frame: location.pathname, select: s.name || s.id,
                      options: [...s.options].map(o => o.text.trim())}))""")
            except Exception:  # noqa: BLE001
                pass
    print("selects:", json.dumps(ctrls)[:4000])


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = find_page(browser, IP)
    try:
        if ACTION == "login" or page is None:
            check_pin(IP)
            cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
            page = page or ctx.new_page()
            page.bring_to_front()
            page.goto(f"https://{IP}/", wait_until="networkidle", timeout=30000)
            page.locator("input[type=text]:visible").first.fill(cred.username)
            page.locator("input[type=password]:visible").first.click()
            page.keyboard.type(cred.password or "", delay=15)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)
        page.bring_to_front()
        if ACTION == "open":  # open a WBM page by its address, e.g. snmp.mwp
            page.goto(f"https://{IP}/?newtab={ARG}", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            print("tabs:", page.eval_on_selector_all(
                "a[href*='mwp']", "els => els.map(e => (e.innerText||'').trim() + '=' + e.getAttribute('href'))")[-25:])
        if ACTION == "goto":
            frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
            text, _, nth = ARG.partition("#")  # "SNMP#2" = second link whose text is exactly SNMP
            clicked = False
            for f in frames:
                loc = f.locator("a").filter(has_text=text)
                exact = [i for i in range(loc.count()) if loc.nth(i).inner_text().strip() == text]
                idx = int(nth) - 1 if nth else 0
                if len(exact) > idx:
                    loc.nth(exact[idx]).click()
                    clicked = True
                    break
            print("clicked:", clicked)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)
        links = []
        for f in page.frames:
            try:
                links += f.eval_on_selector_all("a", "els => els.map(e => (e.innerText||'').trim()).filter(t => t)")
            except Exception:  # noqa: BLE001
                pass
        print("url:", page.url, "| frames:", [f.url for f in page.frames][:6])
        print("links:", links[:150])
        dump(page, (ACTION + "_" + ARG).replace(" ", "_").strip("_"))
        for f in page.frames:
            try:
                txt = " ".join(f.inner_text("body").split())
                if txt:
                    print(f"text[{f.url[-40:]}]:", txt[:1500])
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        print("step failed:", type(e).__name__)
