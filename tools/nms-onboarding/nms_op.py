"""Operation UI (https://192.168.30.11:8443) helper in the visible Edge.
usage: python -I nms_op.py <step>
  credview   Device credential repository: select SW-Ops, Edit, read stored SNMP settings, Cancel
"""
import json
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"C:\Users\Administrator\Documents\Manager_NGP\backend")
from app.core.credentials import CredentialStore  # noqa: E402

OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
STEP = sys.argv[1]
CTRL = """() => [...document.querySelectorAll('select,input')].filter(e => e.offsetParent && e.type !== 'hidden')
    .map(e => (e.placeholder || e.name || e.id || '').slice(0,40) + '=' + (e.type === 'password' ? '(hidden)' :
       e.type === 'checkbox' ? e.checked : (e.tagName === 'SELECT' ? (e.options[e.selectedIndex]||{}).text : e.value)))"""


def op_page(ctx):
    page = next((x for x in ctx.pages if x.url.startswith("https://192.168.30.11:8443")), None) or ctx.new_page()
    page.bring_to_front()
    page.goto(OPB + "home", wait_until="networkidle"); page.wait_for_timeout(2500)
    if page.get_by_placeholder("User name*").count():
        cred = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml").credential("sinec-nms/web-portal")
        u = page.get_by_placeholder("User name*"); u.click(); u.fill(cred.username)
        page.evaluate("() => { const e = document.getElementById('passwordtab'); if (e) e.removeAttribute('readonly'); }")
        page.get_by_placeholder("Password*").click(); page.keyboard.type(cred.password or "", delay=20)
        page.get_by_role("button", name="Log in").click(); page.wait_for_timeout(7000)
    return page


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = op_page(b.contexts[0])
    try:
        if STEP == "credview":
            pg.goto(OPB + "network-administration/device-credentials", wait_until="networkidle"); pg.wait_for_timeout(4000)
            idx = pg.evaluate("""() => { const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('192.168.30.30')); return r ? r.getAttribute('row-index') : null; }""")
            print("row-index:", idx)
            pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(800)
            pg.get_by_text("Edit", exact=True).first.click(); pg.wait_for_timeout(3000)
            pg.screenshot(path=OUT + r"\nms_op_cred_edit_swops.png", full_page=True)
            print("edit form:", json.dumps(pg.evaluate(CTRL)))
            for tab in ("SNMP configuration", "SSH/NETCONF/HTTP(S)"):
                t = pg.get_by_text(tab, exact=True)
                if t.count():
                    t.first.click(); pg.wait_for_timeout(1500); print(tab, json.dumps(pg.evaluate(CTRL)))
            print("text:", " ".join(pg.inner_text("body").split())[-1200:])
            for n in ("Cancel", "Close"):
                c = pg.get_by_role("button", name=n, exact=True)
                if c.count(): c.last.click(); print("closed with", n); break
        if STEP == "credcheck":  # read-only: SNMP read/write settings stored per device
            for ip in sys.argv[2:]:
                pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2500); pg.evaluate("() => { location.hash = '#/network-administration/device-credentials'; }")
                try:
                    pg.wait_for_function(f"() => [...document.querySelectorAll('div[role=row]')].some(r => (r.innerText||'').includes('{ip}'))", timeout=20000)
                except Exception:
                    pass
                pg.wait_for_timeout(1000)
                idx = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('{ip}')); return r ? r.getAttribute('row-index') : null; }}""")
                if idx is None:
                    print(ip, "not in repository"); continue
                print("   rows:", pg.evaluate("() => [...document.querySelectorAll('div[role=row]')].map(r => (r.innerText||'').trim().split('\\n').slice(0,2).join(' ')).filter(t => /\\d+\\.\\d+/.test(t))"))
                sel = pg.locator("div[role=row] input[type=checkbox]:checked")
                for i in range(sel.count()):  # clear any leftover selection (multi-edit shows "No change")
                    sel.nth(0).evaluate("e => e.closest('.ag-selection-checkbox').click()"); pg.wait_for_timeout(300)
                pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(700)
                n = pg.locator("div[role=row][row-index] input[type=checkbox]:checked").count()
                if n != 1:
                    print(ip, f"selection count {n} != 1; skipped"); continue
                pg.get_by_text("Edit", exact=True).first.click(); pg.wait_for_timeout(2500)
                summary = []
                for tab, pre in (("SNMP monitoring", "read"), ("SNMP configuration", "write")):
                    pg.get_by_text(tab, exact=True).first.click(); pg.wait_for_timeout(1200)
                    c = pg.evaluate(CTRL)
                    pick = lambda k: next((x.split("=", 1)[1] for x in c if x.startswith(f"shared_module_{pre}{k}=")), "?")
                    user = next((x.split("=", 1)[1] for x in c if x.startswith("Specify user name=")), "?")
                    summary.append(f"{pre}: v{pick('Version')} {pick('SecurityLevel')} {pick('AuthAlgo')} {pick('EncrypAlgo')} user={user}")
                print(ip, " | ".join(summary))
                pg.get_by_role("button", name="Cancel", exact=True).last.click(); pg.wait_for_timeout(1200)
        if STEP == "credset":  # set one device's SNMP read+write credentials: credset <ip> <SHA-1|SHA-256>
            ip, algo = sys.argv[2], sys.argv[3]
            store = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml")
            pw = {"auth": store.credential("snmpv3/nms").password or "", "priv": store.credential("snmpv3/nms-priv").password or ""}
            pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2500)
            pg.evaluate("() => { location.hash = '#/network-administration/device-credentials'; }")
            pg.wait_for_function(f"() => [...document.querySelectorAll('div[role=row]')].some(r => (r.innerText||'').includes('{ip}'))", timeout=30000)
            idx = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('{ip}')); return r ? r.getAttribute('row-index') : null; }}""")
            pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(700)
            n = pg.locator("div[role=row][row-index] input[type=checkbox]:checked").count()
            if n != 1:
                raise SystemExit(f"selection count {n} != 1")
            pg.get_by_text("Edit", exact=True).first.click(); pg.wait_for_timeout(2500)
            for tab, pre in (("SNMP monitoring", "read"), ("SNMP configuration", "write")):
                pg.get_by_text(tab, exact=True).first.click(); pg.wait_for_timeout(1200)
                pg.locator(f"select[name='shared_module_{pre}Version']:visible").first.select_option(label="3"); pg.wait_for_timeout(700)
                pg.locator(f"select[name='shared_module_{pre}SecurityLevel']:visible").first.select_option(label="AuthPriv"); pg.wait_for_timeout(500)
                pg.locator(f"select[name='shared_module_{pre}AuthAlgo']:visible").first.select_option(label=algo)
                pg.locator(f"select[name='shared_module_{pre}EncrypAlgo']:visible").first.select_option(label="AES-128")
                for ph, val in (("Specify user name", "sinecnms"), ("Specify authentication password", pw["auth"]),
                                ("Specify encryption password", pw["priv"])):
                    f = pg.locator(f"input[placeholder='{ph}']:visible").first
                    f.evaluate("e => e.removeAttribute('readonly')"); f.click(); f.press("Control+a"); f.press("Delete")
                    pg.keyboard.type(val, delay=10); pg.keyboard.press("Tab")
            ok = []
            for tab, pre in (("SNMP monitoring", "read"), ("SNMP configuration", "write")):
                pg.get_by_text(tab, exact=True).first.click(); pg.wait_for_timeout(1000)
                c = pg.evaluate(CTRL)
                ok.append(all(f"shared_module_{pre}{k}" in c for k in ("Version=3", "SecurityLevel=AuthPriv", f"AuthAlgo={algo}", "EncrypAlgo=AES-128"))
                          and "Specify user name=sinecnms" in c)
            pg.screenshot(path=OUT + rf"\nms_op_credset_{ip}.png", full_page=True)
            if all(ok):
                pg.get_by_role("button", name="Save", exact=True).last.click(); pg.wait_for_timeout(3000); print(ip, "saved", algo)
            else:
                pg.get_by_role("button", name="Cancel", exact=True).last.click(); print(ip, "values did not verify -> cancelled", ok)
        if STEP == "credrestore":  # SW-Ops: Restore initial credentials -> verify v3 -> Save
            ip = sys.argv[2] if len(sys.argv) > 2 else "192.168.30.30"
            pg.goto(OPB + "network-administration/device-credentials", wait_until="networkidle"); pg.wait_for_timeout(4000)
            idx = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('div[role=row]')].find(r => (r.innerText||'').includes('{ip}')); return r ? r.getAttribute('row-index') : null; }}""")
            pg.locator(f"div[role=row][row-index='{idx}'] .ag-selection-checkbox").first.click(); pg.wait_for_timeout(800)
            pg.get_by_text("Edit", exact=True).first.click(); pg.wait_for_timeout(3000)
            store = CredentialStore.load(r"C:\Users\Administrator\Documents\Manager_NGP\config\credentials.example.yaml")
            for tab in ("SNMP monitoring", "SNMP configuration"):  # restore is per visible tab
                pg.get_by_text(tab, exact=True).first.click(); pg.wait_for_timeout(1200)
                pg.get_by_text("Restore initial credentials", exact=True).first.click(); pg.wait_for_timeout(2000)
                yes = pg.get_by_role("button", name="Yes", exact=True)
                if yes.count(): yes.last.click(); pg.wait_for_timeout(1500)
                c = pg.evaluate(CTRL)
                if tab == "SNMP configuration" and not any("writeVersion=3" in x for x in c):
                    print("write tab still not v3 after restore -> filling by hand")
                    pg.locator("select[name='shared_module_writeVersion']:visible, select#shared_module_writeVersion:visible").first.select_option(label="3"); pg.wait_for_timeout(800)
                    pg.locator("[name='shared_module_writeSecurityLevel']:visible, #shared_module_writeSecurityLevel:visible").first.select_option(label="AuthPriv"); pg.wait_for_timeout(500)
                    pg.locator("[name='shared_module_writeAuthAlgo']:visible, #shared_module_writeAuthAlgo:visible").first.select_option(label="SHA-256")
                    pg.locator("[name='shared_module_writeEncrypAlgo']:visible, #shared_module_writeEncrypAlgo:visible").first.select_option(label="AES-128")
                    for ph, val in (("Specify user name", "sinecnms"),
                                    ("Specify authentication password", store.credential("snmpv3/nms").password or ""),
                                    ("Specify encryption password", store.credential("snmpv3/nms-priv").password or "")):
                        f = pg.locator(f"input[placeholder='{ph}']:visible").first
                        f.evaluate("e => e.removeAttribute('readonly')"); f.click(); f.press("Control+a"); f.press("Delete")
                        pg.keyboard.type(val, delay=10); pg.keyboard.press("Tab")
            vals = {}
            for tab in ("SNMP monitoring", "SNMP configuration"):
                pg.get_by_text(tab, exact=True).first.click(); pg.wait_for_timeout(1500)
                c = pg.evaluate(CTRL); vals[tab] = c; print(tab, json.dumps(c))
            want = ["Version=3", "SecurityLevel=AuthPriv", "AuthAlgo=SHA-256", "EncrypAlgo=AES-128", "Specify user name=sinecnms"]
            good = all(any(w in x for x in vals[t]) for t in vals for w in want)
            pg.screenshot(path=OUT + r"\nms_op_cred_restored.png", full_page=True)
            if good:
                pg.get_by_role("button", name="Save", exact=True).last.click(); pg.wait_for_timeout(3000)
                print("saved")
            else:
                pg.get_by_role("button", name="Cancel", exact=True).last.click(); print("NOT v3 after restore -> cancelled")
            pg.goto(OPB + "network-administration/device-credentials", wait_until="networkidle"); pg.wait_for_timeout(3000)
            print("repository:", pg.evaluate("""() => [...document.querySelectorAll('div[role=row]')].map(r => (r.innerText||'').trim().replace(/\\s+/g,' ')).filter(t => /\\d+\\.\\d+\\.\\d+\\.\\d+/.test(t))"""))
    except Exception as e:  # noqa: BLE001
        print("failed:", type(e).__name__)
        pg.screenshot(path=OUT + rf"\nms_op_{STEP}_failed.png", full_page=True)





