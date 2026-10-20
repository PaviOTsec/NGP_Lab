"""Starter Set > SNMP settings for discovery: add an SNMPv3 entry (sinecnms, SHA-256/AES-128),
disable the v1 and v2c entries, save only if exactly the v3 entry is enabled; verify after reload.
Expects the Create form to be open already (opened by nms_snmpdisc_create_look2.py)."""
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore  # noqa: E402

BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
NAME = "SNMPv3_sinecnms"
GRID = """() => [...document.querySelectorAll('div[role=row]')].filter(r => r.getAttribute('row-index') !== null && /\\S/.test(r.innerText||''))
    .map(r => [r.getAttribute('row-index'), (r.innerText||'').trim().replace(/\\s+/g,' ')])"""
store = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml")
AUTH, PRIV = store.credential("snmpv3/nms").password or "", store.credential("snmpv3/nms-priv").password or ""


def typ(pg, loc, val):
    loc.evaluate("e => e.removeAttribute('readonly')")
    loc.click(); loc.press("Control+a"); loc.press("Delete"); pg.keyboard.type(val, delay=10); pg.keyboard.press("Tab")


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    try:
        done = pg.locator("#SA_OSS_SNMP_SETTINGS_NEW_DONE")
        if not done.count():
            sys.exit("Create form is not open")
        form = done.locator("xpath=ancestor::*[.//input[@id='name']][1]")
        if pg.locator("input#name").input_value() != NAME:
            typ(pg, pg.locator("input#name"), NAME)
        form.locator("select").first.select_option(label="3"); pg.wait_for_timeout(1200)
        sels = form.locator("select:visible")
        print("v3 selects:", [sels.nth(i).evaluate("e => [...e.options].map(o => o.text.trim()).join('/')") for i in range(sels.count())])
        for i in range(sels.count()):
            opts = sels.nth(i).evaluate("e => [...e.options].map(o => o.text.trim())")
            if "AuthPriv" in opts: sels.nth(i).select_option(label="AuthPriv"); pg.wait_for_timeout(500)
        sels = form.locator("select:visible")
        for i in range(sels.count()):
            opts = sels.nth(i).evaluate("e => [...e.options].map(o => o.text.trim())")
            if "SHA-256" in opts: sels.nth(i).select_option(label="SHA-256")
            if "AES-128" in opts: sels.nth(i).select_option(label="AES-128")
        typ(pg, form.locator("input[placeholder='Specify user name']:visible").first, "sinecnms")
        pw = form.locator("input[placeholder='Enter password']:visible"); print("password fields:", pw.count()); typ(pg, pw.nth(0), AUTH)
        typ(pg, pw.nth(1), PRIV)
        pg.wait_for_timeout(800)
        print("form OK enabled:", done.is_enabled())
        pg.screenshot(path=OUT + r"\nms_snmpdisc_v3_form.png", full_page=True)
        done.click(); pg.wait_for_timeout(2500)
        rows = pg.evaluate(GRID); print("rows:", rows)
        for idx, txt in rows:
            if ("SNMP Settings V1" in txt or "SNMP Settings V2" in txt) and txt.startswith("Enabled"):
                pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(400)
        pg.locator("#snmpDisableButton").click(); pg.wait_for_timeout(1500)
        err = pg.get_by_text("At least one SNMP setting must be activated.")
        if err.count():
            pg.get_by_role("button", name="OK", exact=True).last.click()
            sys.exit("NMS refused (no active setting) â€” not saved")
        rows = pg.evaluate(GRID); print("before save:", rows)
        enabled = [t for _, t in rows if t.startswith("Enabled")]
        if len(enabled) == 1 and NAME in enabled[0] and " 3" in enabled[0]:
            pg.locator("#SA_OSS_footerSave").click(); pg.wait_for_timeout(4000)
            print("saved")
        else:
            pg.locator("#SA_OSS_footerReset").click()
            sys.exit("unexpected state -> Cancel, nothing saved")
        pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
        pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)
        print("after reload:", pg.evaluate(GRID))
        pg.screenshot(path=OUT + r"\nms_snmpdisc_v3_saved.png", full_page=True)
    except Exception as e:  # noqa: BLE001
        print("failed:", type(e).__name__)
        pg.screenshot(path=OUT + r"\nms_snmpdisc_v3_failed.png", full_page=True)

