"""Port mirroring (SPAN) on SW-Ops 192.168.30.30 (SCALANCE XC208G) via WBM, captured as a guide.

Runs in the operator-visible Edge (CDP 127.0.0.1:9222), one phase at a time so each page is
inspected before anything is pressed on it. TLS cert pinned (Backups/tls_pins.json).

Done 2026-10-19 (operator-approved): session 1, sources P0.1-P0.7 both directions, destination
P0.8, Monitor Barrier left on (default). Backup first: Backups/20261019-span/.
Rollback: CLI `configure terminal` -> `no monitor session 1` -> `no monitor` -> `end`.

usage: python -I span_sw_ops.py <backend_dir> <out_dir> <phase>
  p1    login-page shot (fresh window, nothing typed); Layer 2 > Mirroring; General: Create (session 1)
  p2    General: Dest. Port = P0.8, Set Values, read back; open the Port tab
  p3    Port: ingress+egress on P0.1-P0.7, Set Values, read back; General: Mirroring on, read back
  p4    guide-only shots (status; login page from a fresh window), nothing pressed
  meta  guide text (before/verify/undo), no device access
  dump [page]  read-only: print the current page's controls + screenshot to <out>/_debug
Every phase stops at the first unexpected state. Build the Word file with build_docx.py.
"""
from __future__ import annotations

import hashlib
import json
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
PHASE = sys.argv[3]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from guide import All, Guide  # noqa: E402

IP, NAME = "192.168.30.30", "SW-Ops"
SOURCES = range(1, 8)  # P0.1-P0.7 mirrored (ingress + egress) to destination P0.8
URL = f"https://{IP}/"
PINS = BACKEND.parent / "Backups" / "tls_pins.json"


def check_pin() -> None:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((IP, 443), 5)) as s:
        fp = "SHA256:" + hashlib.sha256(s.getpeercert(True)).hexdigest().upper()
    if json.loads(PINS.read_text())[IP] != fp:
        sys.exit(f"TLS cert for {IP} changed ({fp}); not sending credentials")


def login(page) -> None:
    if page.locator("#password:visible").count() == 0:
        return
    check_pin()
    cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    page.locator("#name").fill(cred.username)
    page.locator("#password").click()
    page.keyboard.type(cred.password or "", delay=15)
    page.keyboard.press("Enter")
    page.wait_for_load_state("load", timeout=30000)
    page.wait_for_timeout(2000)


def nav(page, text: str):
    return page.locator(f"xpath=//a[normalize-space(.)='{text}']").filter(visible=True)


def port_tab(page):
    return page.locator("a[href*='mirroring_port.mwp']").first


def tag_port_rows(page):
    """Port names are JS-filled values of <input>s without a type attribute: tag each row and its
    checkboxes so locators can find them."""
    page.evaluate("""() => document.querySelectorAll('input').forEach(e => {
        if (e.type !== 'text' || !/^P0\\.\\d+$/.test(e.value)) return;
        const tr = e.closest('tr');
        tr.setAttribute('data-gg-port', e.value);
        tr.querySelectorAll('input').forEach(c => { if (c.type === 'checkbox') c.setAttribute('data-gg-cb', '1'); });
    })""")
    return lambda n: page.locator(f"tr[data-gg-port='P0.{n}'] [data-gg-cb]")


def dump(page, tag: str) -> None:
    d = OUT / "_debug"
    d.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(d / f"{tag}.png"), full_page=True)
    info = page.evaluate("""() => ({
      inputs: [...document.querySelectorAll('input,select')].filter(e => e.type !== 'hidden' && e.offsetParent)
        .map(e => ({tag: e.tagName, type: e.type, id: e.id, value: e.type === 'password' ? '***' : e.value,
                    checked: e.checked, disabled: e.disabled,
                    options: e.options ? [...e.options].map(o => o.text) : undefined})),
      text: document.querySelector('#contentFrame, .content, body').innerText.slice(-1500)})""")
    print(json.dumps(info, indent=0, ensure_ascii=False)[:8000])


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = next((x for x in ctx.pages if x.url.startswith(URL)), None) or ctx.new_page()
    page.bring_to_front()
    g = Guide(page, OUT, title="Enable Port Mirroring (SPAN) on a SCALANCE Switch",
              intro="Copy all traffic on ports P0.1 to P0.7 to port P0.8, so a capture device "
                    "(Wireshark laptop or IDS sensor) on P0.8 can see it.")
    audit = AuditLog(Settings.load().audit_abs)

    if PHASE == "p1":
        # Login page, shot from a fresh window so no session or credentials are involved.
        fresh = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 900})
        lp = fresh.new_page()
        lp.goto(URL, wait_until="load", timeout=30000)
        lp.wait_for_timeout(2000)
        g.shot("01", f"Open **https://{IP}** in a browser and log in as **admin**.",
               [lp.locator("#name"), lp.locator("#password")], labels=False, page=lp)
        fresh.close()

        page.goto(URL + "?newtab=startpage.mwp", wait_until="load", timeout=30000)
        page.wait_for_timeout(1500)
        login(page)
        page.bring_to_front()
        if nav(page, "Mirroring").count() == 0:
            nav(page, "Layer 2").first.click()
            page.wait_for_timeout(800)
        g.shot("02", "In the menu, open **Layer 2 > Mirroring**.",
               [nav(page, "Layer 2"), nav(page, "Mirroring")])
        nav(page, "Mirroring").first.click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2000)
        if page.locator("#SnMspsConfigMirrorStatus_0").count() != 1:
            sys.exit("not on Mirroring > General; stopping")
        if "0 entries" not in page.inner_text("body"):
            sys.exit("a mirroring session already exists; stopping before Create")
        g.shot("03", "On the **General** tab, click **Create** to add mirroring session 1.",
               [page.locator("#btnCreate")])
        page.locator("#btnCreate").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        audit.record(action="mirroring.session.create", target=NAME, transport="wbm", result="ok",
                     detail={"via": "WBM Mirroring > General > Create"})
        dump(page, "after_create")
    elif PHASE == "p2":
        login(page)
        if page.locator("#SnMspsConfigMirrorStatus_0").count() != 1:
            sys.exit("not on Mirroring > General; stopping")
        dest = page.locator("select:has(option:text-is('P0.8'))")
        if dest.count() != 1:
            sys.exit(f"expected one Dest. Port select, found {dest.count()}; stopping")
        dest.select_option(label="P0.8")
        page.wait_for_timeout(500)
        g.shot("04", "In the session row, set **Dest. Port** to **P0.8**, then click **Set Values**.",
               [dest, page.locator("#btnWrite")])
        page.locator("#btnWrite").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        page.locator("#btnRefresh").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        got = page.locator("select:has(option:text-is('P0.8'))").evaluate("s => s.options[s.selectedIndex].text")
        print("read back Dest. Port:", got)
        audit.record(action="mirroring.destination.set", target=NAME, transport="wbm",
                     result="ok" if got == "P0.8" else "error", detail={"dest_port": got})
        if got != "P0.8":
            sys.exit("destination read-back mismatch; stopping")
        port_tab(page).click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        dump(page, "port_tab")
    elif PHASE == "p3":
        login(page)
        if "mirroring_port" not in page.url and page.locator("#PortMirroringSingleSession_0").count() == 0:
            port_tab(page).click()
            page.wait_for_load_state("load", timeout=30000)
            page.wait_for_timeout(2500)
        if page.locator("#PortMirroringSingleSession_0").input_value() != "1":
            sys.exit("Port tab is not showing session 1; stopping")
        boxes = tag_port_rows(page)
        for n in SOURCES:
            for cb in (boxes(n).nth(0), boxes(n).nth(1)):
                if not cb.is_checked():
                    cb.check()
        if any(boxes(8).nth(i).is_checked() for i in (0, 1)):
            sys.exit("P0.8 (destination) is ticked as a source; stopping")
        g.shot("05", "Open the **Port** tab. Tick **Ingress Mirroring** and **Egress Mirroring** for "
                     "**P0.1 to P0.7** (leave P0.8 clear), then click **Set Values**.",
               [port_tab(page), All(page.locator(
                   ",".join(f"tr[data-gg-port='P0.{n}'] [data-gg-cb]" for n in SOURCES))),
                page.locator("#btnWrite")])
        page.locator("#btnWrite").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        page.locator("#btnRefresh").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        boxes = tag_port_rows(page)
        state = {f"P0.{n}": [boxes(n).nth(i).is_checked() for i in (0, 1)] for n in range(1, 9)}
        print("read back sources [ingress, egress]:", state)
        ok = all(state[f"P0.{n}"] == [True, True] for n in SOURCES) and state["P0.8"] == [False, False]
        audit.record(action="mirroring.sources.set", target=NAME, transport="wbm",
                     result="ok" if ok else "error", detail={"sources": state})
        if not ok:
            sys.exit("source read-back mismatch; stopping")

        page.locator("a[href*='mirroring_general.mwp']").first.click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        mirror = page.locator("#SnMspsConfigMirrorStatus_0")
        mirror.check()
        g.shot("06", "Go back to the **General** tab, tick **Mirroring**, then click **Set Values**.",
               [page.locator("a[href*='mirroring_general.mwp']").first, mirror, page.locator("#btnWrite")])
        page.locator("#btnWrite").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(2500)
        page.locator("#btnRefresh").click()
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(3000)
        enabled = page.locator("#SnMspsConfigMirrorStatus_0").is_checked()
        status = page.locator("input").evaluate_all(
            "els => els.filter(e => e.type === 'text').map(e => e.value).filter(v => /^(in)?active$/i.test(v))")
        print("read back: Mirroring enabled:", enabled, "| session status:", status)
        audit.record(action="mirroring.enable", target=NAME, transport="wbm",
                     result="ok" if enabled else "error", detail={"enabled": enabled, "status": status})
        if not enabled:
            sys.exit("Mirroring checkbox did not stay ticked; stopping")
        dump(page, "after_enable")
    elif PHASE == "p4":  # guide-only shots, nothing pressed
        login(page)
        if not page.locator("#SnMspsConfigMirrorStatus_0").is_checked():
            sys.exit("Mirroring is not enabled; stopping")
        texts = page.locator("input").filter(visible=True)
        status = next(texts.nth(i) for i in range(texts.count()) if texts.nth(i).input_value() == "active")
        g.shot("07", "Check that the session **Status** shows **active**. Port P0.8 now carries a copy "
                     "of all traffic on P0.1 to P0.7.",
               [page.locator("#SnMspsConfigMirrorStatus_0"), status,
                page.locator("select:has(option:text-is('P0.8'))")], labels=False)

        fresh = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 900})
        lp = fresh.new_page()
        lp.goto(URL, wait_until="load", timeout=30000)
        lp.wait_for_timeout(2000)
        fields = lp.locator("input").filter(visible=True)
        main = [fields.nth(i) for i in range(fields.count())
                if fields.nth(i).evaluate("e => e.type") in ("text", "password")
                and fields.nth(i).bounding_box()["x"] > 300]  # the centre form, not the sidebar one
        if len(main) != 2:
            sys.exit(f"expected 2 centre login fields, found {len(main)}")
        b0, b1 = main[0].bounding_box(), main[1].bounding_box()
        x0 = max(0, b0["x"] - 330)
        clip = {"x": x0, "y": max(0, b0["y"] - 140), "width": 760, "height": b1["y"] - b0["y"] + 260}
        g.shot("01", f"Open **https://{IP}** in a browser and log in as **admin**.",
               main, labels=False, page=lp, clip=clip)
        fresh.close()
    elif PHASE == "meta":  # guide text only, no device access
        g.text("08", "Connect the capture device to **P0.8**. The switch saves the change by itself "
                     "within about a minute.")
        g.meta(
            subtitle=f"Example: {NAME} {IP} (SCALANCE XC208G)",
            before=["Pick a **free port** as the mirror port. It stops carrying normal traffic.",
                    "You need the switch's **admin** login."],
            verify={"title": "Check from the CLI (optional)",
                    "text": "Log in over SSH and run:",
                    "code": "show monitor session 1\n\n Session     : 1\n Source Ports\n   Both            : "
                            "Gi0/1,Gi0/2,Gi0/3,Gi0/4,Gi0/5,Gi0/6,Gi0/7\n Destination Ports : Gi0/8\n"
                            " Status            : Active"},
            undo=["**Turn off:** on the General tab, untick **Mirroring** and click **Set Values**.",
                  "**Remove:** tick **Select** on the session row and click **Delete**."],
        )
    elif PHASE == "dump":
        if len(sys.argv) > 4:  # open a tab by its page name first, e.g. mirroring_port
            page.locator(f"a[href*='{sys.argv[4]}.mwp']").first.click()
            page.wait_for_load_state("load", timeout=30000)
            page.wait_for_timeout(2500)
        dump(page, "dump")
    else:
        sys.exit(f"unknown phase {PHASE}")
