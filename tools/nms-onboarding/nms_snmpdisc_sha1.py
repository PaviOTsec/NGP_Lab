"""Starter Set > SNMP settings for discovery: add 'SNMPv3_sha1' (sinecnms, SHA-1/AES-128) for the
OT-FW (SC646 firmware max SHA-1). Save only if the enabled set is exactly the two v3 entries."""
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore  # noqa: E402

BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
NAME = "SNMPv3_sha1"
GRID = """() => [...document.querySelectorAll('div[role=row]')].filter(r => r.getAttribute('row-index') !== null && /\\S/.test(r.innerText||''))
    .map(r => (r.innerText||'').trim().replace(/\\s+/g,' '))"""
store = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml")
AUTH, PRIV = store.credential("snmpv3/nms").password or "", store.credential("snmpv3/nms-priv").password or ""


def typ(pg, loc, val):
    loc.evaluate("e => e.removeAttribute('readonly')")
    loc.click(); loc.press("Control+a"); loc.press("Delete"); pg.keyboard.type(val, delay=10); pg.keyboard.press("Tab")


def open_group(pg):
    pg.goto(BASE + "system-administration/operation-system-settings", wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("SNMP settings for discovery", exact=True).first.click(); pg.wait_for_timeout(3000)


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    try:
        open_group(pg)
        rows = pg.evaluate(GRID); print("before:", rows)
        if any(NAME in r for r in rows):
            sys.exit("entry already exists")
        rects = pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e => e.offsetParent && (e.innerText||'').trim() === 'Create' && e.children.length <= 2)
            .map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)]; })""")
        x, y = next((cx, cy) for cx, cy in rects if cx > 700)
        pg.mouse.click(x, y); pg.wait_for_timeout(2500)
        done = pg.locator("#SA_OSS_SNMP_SETTINGS_NEW_DONE")
        form = done.locator("xpath=ancestor::*[.//input[@id='name']][1]")
        typ(pg, pg.locator("input#name"), NAME)
        form.locator("select").first.select_option(label="3"); pg.wait_for_timeout(1200)
        sels = form.locator("select:visible")
        for i in range(sels.count()):
            if "AuthPriv" in sels.nth(i).evaluate("e => [...e.options].map(o => o.text.trim())"):
                sels.nth(i).select_option(label="AuthPriv"); pg.wait_for_timeout(500)
        sels = form.locator("select:visible")
        for i in range(sels.count()):
            opts = sels.nth(i).evaluate("e => [...e.options].map(o => o.text.trim())")
            if "SHA-1" in opts: sels.nth(i).select_option(label="SHA-1")
            if "AES-128" in opts: sels.nth(i).select_option(label="AES-128")
        typ(pg, form.locator("input[placeholder='Specify user name']:visible").first, "sinecnms")
        pw = form.locator("input[placeholder='Enter password']:visible")
        typ(pg, pw.nth(0), AUTH); typ(pg, pw.nth(1), PRIV)
        pg.wait_for_timeout(800)
        pg.screenshot(path=OUT + r"\nms_snmpdisc_sha1_form.png", full_page=True)
        if not done.is_enabled():
            sys.exit("form not valid — nothing saved")
        done.click(); pg.wait_for_timeout(2500)
        rows = pg.evaluate(GRID); print("unsaved:", rows)
        enabled = sorted(r.split(" ")[1] for r in rows if r.startswith("Enabled"))
        if enabled == sorted(["SNMPv3_sinecnms", NAME]) and any(NAME in r and r.endswith(" 3") for r in rows):
            pg.locator("#SA_OSS_footerSave").click(); pg.wait_for_timeout(4000); print("saved")
        else:
            pg.locator("#SA_OSS_footerReset").click(); sys.exit(f"unexpected enabled set {enabled} — cancelled")
        open_group(pg); print("after reload:", pg.evaluate(GRID))
    except Exception as e:  # noqa: BLE001
        print("failed:", type(e).__name__)
        pg.screenshot(path=OUT + r"\nms_snmpdisc_sha1_failed.png", full_page=True)
