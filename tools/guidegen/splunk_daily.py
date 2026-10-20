"""Splunk daily-operations guide: READ-ONLY tour of Splunk Web on DMZH1_SIEM, captured as a guide.

Uses the Splunk tab in the operator-visible Edge (CDP 127.0.0.1:9222) at a fixed 1440x900
viewport so screenshots stay readable in Word. Nothing is saved, edited or acknowledged: only
page loads, menu opens, and ad-hoc searches (which are read-only).
Identity check (NTLM: 10.1.20.15 must answer as DMZH1SIEM) before the credential is sent.

usage: python -I -X utf8 splunk_daily.py <backend_dir> <out_dir> <phase> [arg]
  look <path>   read-only: open /en-US<path>, print panel titles / menus, screenshot to <out>/_debug
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
PHASE = sys.argv[3]
ARG = sys.argv[4] if len(sys.argv) > 4 else ""
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402

from app.core import identity  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from guide import All, Guide  # noqa: E402

HOST = "10.1.20.15"
BASE = f"http://{HOST}:8000/en-US"
VIEW = {"width": 1440, "height": 900}

LOOK_JS = """() => {
  const vis = el => !!(el.offsetParent || el.getClientRects().length);
  const t = el => (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
  const panels = [...document.querySelectorAll('.dashboard-panel, [data-test=panel], .panel-title, h2, h3')]
     .filter(vis).map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 60) + ' :: ' + t(e).slice(0, 80)).slice(0, 60);
  const nav = [...document.querySelectorAll('header a, nav a, [role=menubar] a, [role=menuitem], [data-test*=app-bar] a, button')]
     .filter(vis).map(t).filter(x => x && x.length < 40);
  return {url: location.href, title: document.title, panels, nav: [...new Set(nav)].slice(0, 60)};
}"""


def ensure_login(pg) -> None:
    if "/account/login" not in pg.url and pg.locator("input[name=password]").count() == 0:
        return
    identity.check("DMZH1SIEM", asyncio.run(identity.probe_identity(HOST, timeout=8)), HOST)
    cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("splunk/admin")
    pg.fill("input[name=username]", cred.username)
    pg.click("input[name=password]")
    pg.keyboard.type(cred.password or "", delay=15)
    pg.keyboard.press("Enter")
    pg.wait_for_load_state("domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)


def panel(pg, title: str):
    return pg.locator(".dashboard-panel").filter(has=pg.locator("h2.panel-title", has_text=title)).first


def top(pg, loc, margin: int = 70) -> None:
    """Scroll so the element sits near the top of the viewport."""
    loc.evaluate("e => e.scrollIntoView({block: 'start'})")
    pg.evaluate(f"() => window.scrollBy(0, -{margin})")
    pg.wait_for_timeout(1200)


def around(pg, targets, pad_x: int, pad_y: int) -> dict:
    boxes = [t.bounding_box() for t in targets]
    vw = pg.viewport_size
    x0 = max(0, min(b["x"] for b in boxes) - pad_x)
    y0 = max(0, min(b["y"] for b in boxes) - pad_y)
    x1 = min(vw["width"], max(b["x"] + b["width"] for b in boxes) + pad_x)
    y1 = min(vw["height"], max(b["y"] + b["height"] for b in boxes) + pad_y)
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def menu_clip(pg, button, item) -> dict:
    """Top-bar menu: from the top of the page to below the opened item, around the button."""
    b, i = button.bounding_box(), item.bounding_box()
    x0 = max(0, min(b["x"], i["x"]) - 420)
    x1 = min(pg.viewport_size["width"], max(b["x"] + b["width"], i["x"] + i["width"]) + 200)
    return {"x": x0, "y": 0, "width": x1 - x0, "height": i["y"] + i["height"] + 70}


def dashboard(pg, query: str = "") -> None:
    goto(pg, "/app/lab_security/lab_security_overview" + query, settle=4000)
    for _ in range(30):  # wait until every panel's search has finished
        if pg.locator(".dashboard-panel").count() >= 18 and pg.evaluate(
                "() => [...document.querySelectorAll('.dashboard-panel')].every(p => !/Search is (running|waiting|queued)/i.test(p.innerText))"):
            break
        pg.wait_for_timeout(1000)
    pg.wait_for_timeout(2500)


def goto(pg, path: str, settle: int = 6000) -> None:
    pg.goto(BASE + path, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(2500)
    if "/account/login" in pg.url:
        ensure_login(pg)
        pg.goto(BASE + path, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(settle)


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    pg = next((x for x in ctx.pages if x.url.startswith(f"http://{HOST}:8000")), None) or ctx.new_page()
    pg.bring_to_front()
    pg.set_viewport_size(VIEW)
    pg.set_default_timeout(20000)  # fail a stuck step instead of hanging
    g = Guide(pg, OUT, title="Splunk Daily Operations Guide",
              intro="How to check the lab's security monitoring each day. Everything here is read-only: "
                    "it does not change Splunk.")
    if PHASE == "diagram":  # setup.html -> setup.png (2x for print)
        dctx = browser.new_context(viewport={"width": 1400, "height": 700}, device_scale_factor=2)
        dp = dctx.new_page()
        dp.goto((OUT / "setup.html").resolve().as_uri(), wait_until="load")
        dp.locator("#d").screenshot(path=str(OUT / "setup.png"))
        dctx.close()
        print("wrote", OUT / "setup.png")
    elif PHASE == "c1":
        if (OUT / "01.png").exists():
            print("01 already captured; skipping the fresh login window (saves RAM)")
        else:
            fresh = browser.new_context(viewport=VIEW)  # login page without the session: nothing typed
            lp = fresh.new_page()
            lp.goto(f"{BASE}/account/login", wait_until="domcontentloaded", timeout=60000)
            lp.wait_for_timeout(3000)
            fields = [lp.locator("input[name=username]"), lp.locator("input[name=password]")]
            g.shot("01", f"Open **http://{HOST}:8000** in a browser and log in with your Splunk account.",
                   fields, labels=False, page=lp, clip=around(lp, fields, 260, 170), group="Open the dashboard")
            fresh.close()
        goto(pg, "/app/launcher/home")
        app = pg.get_by_text("Lab Security", exact=True).filter(visible=True).first.locator(
            "xpath=ancestor-or-self::*[self::a or self::button or @role='button' or @role='link' or @role='menuitem' or self::li][1]")
        g.shot("02", "On the home page, click **Lab Security** in the Apps list. It opens the "
                     "**Lab Security Overview** dashboard.", [app], min_w=760, min_h=480)

        dashboard(pg)
        tr = pg.locator("button, [role=button]").filter(has_text="Last 24 hours").filter(visible=True).first
        hostdd = pg.locator("button, [role=button]").filter(has_text="All hosts").filter(visible=True).first
        g.shot("03", "**1** Time range: last 24 hours by default; change it to look further back. "
                     "**2** Host: show the Windows panels for one server only. "
                     "**3** Hosts reporting should be **9** and green. "
                     "**4** Alerts fired: above 0 turns red; check the alerts (steps 9 to 11).",
               [tr, hostdd, panel(pg, "Hosts reporting"), panel(pg, "Alerts fired")],
               min_w=VIEW["width"], pad=16, group="Read the dashboard")
        fwd, rec = panel(pg, "Forwarder status"), panel(pg, "Recent alerts (LAB + ESCU)")
        top(pg, fwd)
        g.shot("04", scroll=False, text= "**1** Forwarder status: every server should be **OK**. **SILENT** means nothing "
                     "received for 15 minutes (server off, forwarder stopped, or network). "
                     "**2** Recent alerts: newest first.", targets=[fwd, rec], crop="band", pad=24)
    elif PHASE == "c2":
        dashboard(pg)
        nd, br, na = (panel(pg, "Network devices (via Scribbler)"), panel(pg, "Scribbler bridge"),
                      panel(pg, "Recent network alerts"))
        top(pg, nd)
        g.shot("05", "**1** Network devices (scroll the table right to see **status**): each should be "
                     "**OK**. **QUIET** = no logs for 48 hours, "
                     "**NEVER** = not sending logs yet. **2** Scribbler bridge must show **ok**. "
                     "**3** Recent network alerts (LAB NET).", [nd, br, na], crop="band", pad=24, scroll=False)
        ch, ev, dn = (panel(pg, "Network configuration changes"), panel(pg, "Switch / OT-FW events"),
                      panel(pg, "Top denied sources"))
        top(pg, ch)
        g.shot("06", "**1** Network configuration changes: who changed what on a switch or firewall. Each "
                     "should be planned work you know about. **2** Switch events by type (logins, links, "
                     "config). **3** Top denied sources: addresses the firewalls blocked most.",
               [ch, ev, dn], crop="band", pad=24, scroll=False)
        dashboard(pg, "?form.t.earliest=-7d%40d&form.t.latest=now&form.host=*")  # quiet day: show a week
        fl, ac = panel(pg, "Failed logons by account"), panel(pg, "Account and group changes")
        rl, sv = panel(pg, "Remote and interactive logons"), panel(pg, "Services installed")
        top(pg, fl)
        g.shot("07", "Windows activity: **1** failed logons, **2** new users and group changes. "
                     "(Shown for the last 7 days; on a quiet day these panels say *No results found*, "
                     "which is normal.)", [fl, ac], crop="band", pad=24, scroll=False)
        top(pg, rl)
        g.shot("08", "**1** RDP and console logons, **2** newly installed services. Look for accounts, "
                     "sources or times you do not expect.", [rl, sv], crop="band", pad=24, scroll=False)
    elif PHASE == "c3":  # alerts: open menus and result views only; never Edit / Delete
        dashboard(pg)
        act = pg.get_by_role("button", name=re.compile(r"^\s*Activity")).filter(visible=True).first
        act.click()
        pg.wait_for_timeout(1500)
        item = pg.get_by_text("Triggered Alerts", exact=True).filter(visible=True).first
        g.shot("09", "Click the **Activity** icon at the top, then **Triggered Alerts**.", [act, item],
               clip=menu_clip(pg, act, item), group="Check the alerts")
        item.click()
        pg.wait_for_load_state("domcontentloaded")
        pg.wait_for_timeout(5000)
        if "eai%3Aacl.app=lab_security" not in pg.url:
            print("Triggered Alerts opened outside the app context:", pg.url)
            goto(pg, "/app/lab_security/triggered_alerts")
        appdd = pg.locator("button, [role=button]").filter(has_text="Lab Security").filter(visible=True).first
        view = pg.get_by_text("View Results", exact=True).filter(visible=True).first
        g.shot("10", "Check **App** shows **Lab Security**: the list then has the LAB, LAB NET and ESCU "
                     "alerts, newest on top. Click **View Results** to see what fired an alert. "
                     "Do not use **Edit Alert** or **Delete**.", [appdd, view], min_w=VIEW["width"], min_h=400)
        with ctx.expect_page(timeout=20000) as newp:
            view.click()
        rp = newp.value
        rp.set_viewport_size(VIEW)
        rp.wait_for_load_state("domcontentloaded")
        rp.wait_for_timeout(9000)
        res = rp.locator("table:has(th)").filter(visible=True).first  # the results, not the search bar
        g.shot("11", "The results open in a new tab: the time, the device or host, and what happened. "
                     "Compare it with planned work; tell the lab operator about anything unexpected.",
               [res], page=rp, crop="viewport", labels=False)
        rp.close()
    elif PHASE == "c4":  # an ad-hoc search (read-only)
        goto(pg, "/app/lab_security/search")
        bar = pg.locator(".ace_editor, [data-test=search-input], textarea").filter(visible=True).first
        bar.click()
        pg.keyboard.type("index=netdev host=192.168.30.30", delay=30)
        tp = pg.locator("button, [role=button]").filter(has_text="Last 24 hours").filter(visible=True).first
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(9000)
        g.shot("12", "Click **Search** in the left bar. Type a search that starts with `index=`, pick the "
                     "time range, press **Enter**. Example: everything switch SW-Ops (192.168.30.30) logged "
                     "in the last 24 hours.", [bar, tp], crop="viewport", group="Search the logs")
        host = pg.locator("a, button, [role=button]").filter(has_text="host").filter(visible=True).first
        g.shot("13", "Each event shows its time and message. Click a field on the left, such as **host**, "
                     "to see its values; click a value to narrow the search.", [host], crop="viewport",
               labels=False)
    elif PHASE == "meta":  # guide text only, no Splunk access
        g.meta(
            subtitle=f"Lab SIEM: DMZH1_SIEM {HOST}  |  Splunk Enterprise 10.6",
            steps_heading="Step by step",
            sections_before=[
                {"heading": "The setup in brief", "items": [
                    {"image": "setup.png", "width_cm": 16.5},
                    {"table": [["Index", "What is in it", "Comes from"],
                               ["`wineventlog`", "Windows event logs: logons, accounts, services, PowerShell, "
                                "Defender", "9 Windows servers"],
                               ["`sysmon`", "Process starts, network connections, file and registry activity",
                                "9 Windows servers"],
                               ["`netdev`", "Switch and firewall logs: logins, links, config changes, denied "
                                "traffic", "8 switches + 3 firewalls, via Scribbler"]],
                     "widths": [2.6, 9.4, 5.0]},
                    {"bullets": [
                        "**Times in Splunk are UTC.** Lab local time is UTC + 8 hours "
                        "(06:00 in Splunk = 14:00 local).",
                        "Alerts are checked every 5 minutes (ESCU every hour). There is no e-mail: "
                        "alerts only show in Splunk.",
                        "This guide only looks at data. Nothing in it changes Splunk.",
                    ]},
                ]},
                {"heading": "Daily check (about 10 minutes)", "items": [
                    {"numbered": [
                        "Open the **Lab Security Overview** dashboard (steps 1 and 2).",
                        "**Hosts reporting** shows **9** and every forwarder is **OK** (steps 3 and 4).",
                        "Every network device is **OK** and the Scribbler bridge shows **ok** (step 5).",
                        "**Alerts fired** is **0**, or open each new alert (steps 9 to 11).",
                        "Skim config changes, failed logons, account changes and logons for anything "
                        "unexpected (steps 6 to 8).",
                        "Write down anything odd and tell the lab operator.",
                    ]},
                ]},
            ],
            sections_after=[
                {"heading": "When something is not green", "items": [
                    {"table": [["You see", "Usually means", "What to do"],
                               ["Hosts reporting below 9, or a host **SILENT**",
                                "Server off or restarting, forwarder stopped, or network path down",
                                "Check the server is running. Still silent after 15 minutes: tell the operator."],
                               ["Network device **QUIET** or **NEVER**",
                                "Device off, logging off, or the path to Scribbler broken. Quiet switches "
                                "log very little, so QUIET can be normal",
                                "Tell the operator if it stays QUIET for more than a day."],
                               ["Scribbler bridge **STALE**, **error** or **NO HEARTBEAT**",
                                "Network logs are no longer reaching Splunk",
                                "Tell the operator (log server DMZH1_LogServer)."],
                               ["**Alerts fired** above 0", "A rule matched",
                                "Open it (steps 9 to 11). Planned work: note it. Otherwise tell the operator."],
                               ["A config change you did not expect", "Someone changed a switch or firewall",
                                "Note device, user and time; tell the operator."]],
                     "widths": [4.6, 6.0, 6.4]},
                ]},
                {"heading": "Useful searches", "items": [
                    {"p": "Paste into **Search**, set the time range, press **Enter**."},
                    {"table": [["Search", "Shows"],
                               ["index=wineventlog | stats count by host", "Events per Windows server"],
                               ["index=wineventlog host=DMZH2DC", "Everything from one server"],
                               ["index=netdev host=192.168.30.30", "Everything from one network device (by IP)"],
                               ["index=netdev sourcetype=scalance:syslog | stats count by netdev_name event_class",
                                "Switch events by device and type"],
                               ["index=wineventlog `lab_win(Security)` EventCode=4625 | `lab_failed_logon_fields` "
                                "| stats count by host user src reason", "Failed logons: who, from where, why"],
                               ["index=sysmon host=DMZH1MSSQL | stats count by EventCode",
                                "Sysmon activity on one server (1 = process start, 3 = network)"]],
                     "widths": [11.0, 6.0], "mono": [0]},
                ]},
                {"heading": "Please don't", "items": [
                    {"bullets": [
                        "Edit, disable or delete alerts, dashboards or triggered alerts.",
                        "Restart Splunk or a forwarder. Tell the operator instead.",
                        "Search **All time** without a reason: it is slow. Last 24 hours or 7 days is enough.",
                        "Forget `index=`: without it a search finds nothing.",
                    ]},
                ]},
            ],
        )
    elif PHASE == "look":
        goto(pg, ARG)
        info = pg.evaluate(LOOK_JS)
        print(json.dumps(info, indent=0, ensure_ascii=False)[:6000])
        d = OUT / "_debug"
        d.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(d / "look.png"))
    else:
        sys.exit(f"unknown phase {PHASE}")
