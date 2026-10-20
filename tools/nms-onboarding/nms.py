"""SINEC NMS in the operator-visible Edge (CDP 127.0.0.1:9222). READ-ONLY steps.

usage: python -I nms.py <backend_dir> <out_dir> <step>
  login        log in (TLS cert pinned first)
  v3options    Initial credentials: switch Version to 3 (NOT saved), read options, Cancel
  scanranges   Operations: open "Edit scan ranges", read the table, close without saving
Exceptions print their type only (Playwright call logs echo typed values).
"""
import hashlib
import json
import re
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
STEP = sys.argv[3]
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = "192.168.30.11"
PIN = "4F32B17B125081DA944C7620EF2B11ADBBBAE4C553B84630131206C697491883"  # read 2026-10-12
BASE = f"https://{HOST}/sinecnmsWebappControl/UI/#/"
OUT.mkdir(parents=True, exist_ok=True)


def check_pin() -> None:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((HOST, 443), 5)) as s:
        fp = hashlib.sha256(s.getpeercert(True)).hexdigest().upper()
    if fp != PIN:
        sys.exit(f"NMS TLS cert changed ({fp}); not sending credentials")


def controls(page) -> list:
    return page.evaluate("""() => {
      const lab = el => { const r = el.closest('div,td,tr'); return r ? r.innerText.split('\\n')[0].trim().slice(0,60) : ''; };
      const out = [];
      document.querySelectorAll('select').forEach(s => { if (s.offsetParent) out.push({select: lab(s),
         value: s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : '', options: [...s.options].map(o => o.text.trim())}); });
      document.querySelectorAll('input').forEach(i => { if (i.offsetParent && i.type !== 'hidden') out.push({input: lab(i) || i.placeholder || i.name, type: i.type,
         value: i.type === 'password' ? '(hidden)' : i.value}); });
      return out; }""")


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = next((x for x in ctx.pages if x.url.startswith(f"https://{HOST}/")), None)
    try:
        if page is not None:  # a stale tab may still show an app URL after the session expired
            page.goto(BASE + "home", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
        if page is None or STEP == "login" or "login" in page.url or page.get_by_placeholder("User name*").count():
            check_pin()
            cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("sinec-nms/web-portal")
            page = page or ctx.new_page()
            page.bring_to_front()
            page.goto(BASE + "login", wait_until="networkidle", timeout=60000)
            u = page.get_by_placeholder("User name*")
            u.click()
            u.fill(cred.username)
            page.evaluate("() => document.getElementById('passwordtab').removeAttribute('readonly')")
            page.get_by_placeholder("Password*").click()
            page.keyboard.type(cred.password or "", delay=20)
            page.get_by_role("button", name="Log in").click()
            page.wait_for_timeout(6000)
            print("logged in:", "home" in page.url)
        page.bring_to_front()

        if STEP == "v3options":
            page.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.get_by_text("SNMP monitoring", exact=True).click()
            page.wait_for_timeout(1000)
            ver = page.locator("select:visible").first
            print("before:", json.dumps(controls(page)))
            ver.select_option(label="3")  # form only â€” NOT saved
            page.wait_for_timeout(1500)
            print("v3 form:", json.dumps(controls(page), indent=0))
            page.screenshot(path=str(OUT / "nms_v3_options.png"), full_page=True)
            page.get_by_role("button", name="Cancel").click()
            page.wait_for_timeout(1500)
            print("after Cancel:", json.dumps(controls(page)))
            for tab in ("SNMP configuration", "SSH/NETCONF/HTTP(S)"):
                page.get_by_text(tab, exact=True).click()
                page.wait_for_timeout(1500)
                print(f"[{tab}]", json.dumps(controls(page)))
                page.screenshot(path=str(OUT / f"nms_{tab.split('/')[0].replace(' ', '_')}.png"), full_page=True)

        if STEP == "scanranges":
            page.goto(BASE + "system-administration/operation-connectivity-management/operation-management",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.get_by_text("Edit scan ranges", exact=True).click()
            page.wait_for_timeout(4000)
            page.screenshot(path=str(OUT / "nms_scan_ranges.png"), full_page=True)
            print("text:", " ".join(page.inner_text("body").split())[:4000])
            page.get_by_role("button", name="Cancel").last.click()  # close without saving
            page.wait_for_timeout(1500)
            print("dialog closed:", page.get_by_text("Scan ranges (", exact=False).count() == 0)

        if STEP == "backupinfo":  # Control administration > System backup settings (read-only)
            page.goto(BASE + "system-administration/control-administration/system-information",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            page.get_by_text("System backup settings", exact=True).first.click()
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / "nms_backup_settings.png"), full_page=True)
            print("controls:", json.dumps(controls(page)))
            print("text:", " ".join(page.inner_text("body").split())[:3000])

        if STEP in ("scanranges_dom", "disable_l2_ranges"):
            page.goto(BASE + "system-administration/operation-connectivity-management/operation-management",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            page.get_by_text("Edit scan ranges", exact=True).click()
            page.wait_for_timeout(3000)
            L2 = ("192.168.20.1", "192.168.1.1")

            def ranges() -> dict:  # firstIP -> status, from the ag-grid rows
                return page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('div[role=row]')]
                    .map(r => [r.querySelector('[col-id=firstIP]'), r.querySelector('[col-id=customStatus]'), r.querySelector('[col-id=subgroupName]')])
                    .filter(([f]) => f && /\\d+\\.\\d+/.test(f.innerText))
                    .map(([f, s, n]) => [f.innerText.trim(), (s ? s.innerText.trim() : '?') + ' / ' + (n ? n.innerText.trim() : '')]))""")
            print("ranges:", ranges())
            if STEP == "disable_l2_ranges":
                for first_ip in L2:
                    box = page.locator(f"div[role=row]:has([col-id=firstIP] span:text-is('{first_ip}')) "
                                       "[col-id=action] input[type=checkbox]")
                    assert box.count() == 1, f"checkbox for {first_ip}: {box.count()}"
                    box.first.check(force=True)
                    page.wait_for_timeout(400)
                page.get_by_text("Disable", exact=True).last.click()
                page.wait_for_timeout(2000)
                after = ranges()
                print("after Disable (not yet OK):", after)
                page.screenshot(path=str(OUT / "nms_ranges_before_ok.png"), full_page=True)
                expect_ok = all(after.get(ip, "").startswith("Disabled") for ip in L2) and all(
                    v.startswith("Enabled") for ip, v in after.items() if ip not in L2)
                if not expect_ok:
                    print("unexpected state -> Cancel (nothing saved)")
                    page.get_by_role("button", name="Cancel").last.click()
                else:
                    page.get_by_role("button", name="OK", exact=True).last.click()
                    page.wait_for_timeout(4000)
                    page.get_by_text("Edit scan ranges", exact=True).click()
                    page.wait_for_timeout(3000)
                    print("re-opened (saved state):", ranges())
                    page.screenshot(path=str(OUT / "nms_ranges_after.png"), full_page=True)
                    page.get_by_role("button", name="Cancel").last.click()
            else:
                page.get_by_role("button", name="Cancel").last.click()

        if STEP == "set_v3_creds":  # Starter Set > Initial credentials, both SNMP tabs -> v3
            store = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
            auth_pw = store.credential("snmpv3/nms").password or ""
            priv_pw = store.credential("snmpv3/nms-priv").password or ""

            def open_tab(tab):
                page.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)
                page.get_by_text("Initial credentials", exact=True).first.click()
                page.wait_for_timeout(1500)
                page.get_by_text(tab, exact=True).click()
                page.wait_for_timeout(1500)

            def type_into(placeholder, value):
                f = page.locator(f"input[placeholder='{placeholder}']:visible").first
                f.evaluate("e => e.removeAttribute('readonly')")
                f.click()
                f.press("Control+a")
                page.keyboard.type(value, delay=10)

            for tab in ("SNMP monitoring", "SNMP configuration"):
                open_tab(tab)
                sel = page.locator("select:visible")
                sel.nth(0).select_option(label="3")
                page.wait_for_timeout(800)
                sel = page.locator("select:visible")
                sel.nth(1).select_option(label="AuthPriv")
                page.wait_for_timeout(500)
                sel.nth(2).select_option(label="SHA-256")
                sel.nth(3).select_option(label="AES-128")
                type_into("Specify user name", "sinecnms")
                type_into("Specify authentication password", auth_pw)
                type_into("Specify encryption password", priv_pw)
                page.screenshot(path=str(OUT / f"nms_v3_{tab.split()[1]}_before_save.png"), full_page=True)
                page.get_by_role("button", name="Save", exact=True).click()
                page.wait_for_timeout(4000)
                body = " ".join(page.inner_text("body").split())
                msg = re.findall(r"(?i)[^.]{0,80}(saved|success|error|invalid|failed)[^.]{0,80}", body)
                print(f"[{tab}] after Save:", msg[:3])
            for tab in ("SNMP monitoring", "SNMP configuration"):  # read back after reload
                open_tab(tab)
                print(f"[{tab}] stored:", json.dumps([c for c in controls(page) if "select" in c or
                      c.get("input") in ("Specify user name", "Specify port", "Specify retries")]))
                page.screenshot(path=str(OUT / f"nms_v3_{tab.split()[1]}_after.png"), full_page=True)

        if STEP == "scan_dialog":  # look only: open Start network scan, read, Cancel
            page.goto(BASE + "system-administration/operation-connectivity-management/operation-management",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            page.get_by_text("Start network scan", exact=True).click()
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / "nms_scan_dialog.png"), full_page=True)
            dlg = page.locator("[role=dialog], .modal, mat-dialog-container, .p-dialog").last
            print("dialog text:", " ".join((dlg.inner_text() if dlg.count() else page.inner_text("body")).split())[:2000])
            print("controls:", json.dumps(controls(page)))
            for name in ("Cancel", "No", "Close"):
                b = page.get_by_role("button", name=name, exact=True)
                if b.count():
                    b.last.click()
                    print("closed with", name)
                    break

        if STEP == "backupexec":  # Operations > System backup execution tab (read-only look)
            page.goto(BASE + "system-administration/operation-connectivity-management/operation-management",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            page.get_by_text("System backup execution", exact=False).first.click()
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / "nms_backup_execution.png"), full_page=True)
            print("buttons:", page.eval_on_selector_all("button", "els => els.map(e => (e.innerText||'').trim() + (e.disabled ? ' (disabled)' : '')).filter(Boolean)"))
            print("text:", " ".join(page.inner_text("body").split())[:2500])

        if STEP == "discovery":  # Starter Set > Discovery settings (read-only)
            page.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.get_by_text("Discovery settings", exact=True).click()
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "nms_discovery_settings.png"), full_page=True)
            print("controls:", json.dumps(controls(page)))
            pe = page.locator("text=Parameter editor").locator("xpath=ancestor::*[3]")
            print("text:", " ".join((pe.first.inner_text() if pe.count() else page.inner_text("body")).split())[:3000])
    except Exception as e:  # noqa: BLE001
        print("step failed:", type(e).__name__)
        page and page.screenshot(path=str(OUT / f"nms_{STEP}_failed.png"))



