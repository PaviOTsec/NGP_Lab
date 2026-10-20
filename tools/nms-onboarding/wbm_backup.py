"""SCALANCE WBM native backups in the operator-visible Edge: System > Load&Save > HTTP,
press ONLY the "Save" button (= download to MC01) on the rows Config and ConfigPack.
Never touches Load/Delete. TLS cert pinned (first contact recorded).

usage: python -I wbm_backup.py <backend_dir> <out_dir> <name=ip> ...
"""
import hashlib
import json
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
DEVICES = [a.split("=", 1) for a in sys.argv[3:]]
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PINS = OUT.parent / "tls_pins.json"
ROWS = ["Config", "ConfigPack"]


def tls_fp(host: str) -> str:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((host, 443), 5)) as s:
        return "SHA256:" + hashlib.sha256(s.getpeercert(True)).hexdigest().upper()


cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
pins = json.loads(PINS.read_text()) if PINS.exists() else {}
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    for name, ip in DEVICES:
        page = None
        try:
            fp = tls_fp(ip)
            if ip in pins and pins[ip] != fp:
                print(f"{name}: TLS cert changed; skipped (no credentials sent)")
                continue
            pins[ip] = fp
            PINS.write_text(json.dumps(pins, indent=1))
            page = next((x for x in ctx.pages if x.url.startswith(f"https://{ip}")), None) or ctx.new_page()
            page.bring_to_front()
            page.goto(f"https://{ip}/", wait_until="networkidle", timeout=30000)
            if page.locator("input[type=password]:visible").count():
                page.locator("input[type=text]:visible").first.fill(cred.username)
                page.locator("input[type=password]:visible").first.click()
                page.keyboard.type(cred.password or "", delay=15)
                page.keyboard.press("Enter")
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(1500)
            page.goto(f"https://{ip}/?newtab=loadandsave_http.mwp", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            d = OUT / name
            d.mkdir(parents=True, exist_ok=True)
            for row in ROWS:
                # Type names are readonly <input>s in the first cell; Save = download (class "dl")
                btn = page.locator(f"tr:has(> td:first-child > input[readonly][value='{row}']) "
                                   f"input.dl[type=button][value='Save']")
                if btn.count() != 1 or btn.first.is_disabled():
                    print(f"{name}: {row}: Save button not found/enabled (count={btn.count()})")
                    continue
                with page.expect_download(timeout=60000) as dl:
                    btn.first.click()
                ts = __import__("time").strftime("%Y%m%d-%H%M%S")
                target = d / f"{name}_{ip}_{ts}_wbm_{row}-{dl.value.suggested_filename}"
                dl.value.save_as(target)
                data = target.read_bytes()
                print(f"{name}: {row} -> {target.name} {len(data)} bytes sha256 {hashlib.sha256(data).hexdigest()[:16]}")
        except Exception as e:  # noqa: BLE001
            print(f"{name}: failed {type(e).__name__}")
        finally:  # free MC01 RAM: one device tab at a time
            if page is not None and not page.is_closed():
                page.close()
