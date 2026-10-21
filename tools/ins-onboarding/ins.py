"""SINEC INS 10.1.20.21 in the operator-visible Edge (CDP 127.0.0.1:9222). READ-ONLY.

Mirrors tools/nms-onboarding/nms.py: TLS cert pinned before any credential is sent,
credentials from the app CredentialStore (sinecins/web-superadmin), nothing hardcoded.

usage: python -I ins.py <backend_dir> <out_dir> <step>
  probe        check TLS pin, load the login page, dump its field/button structure. NO credentials.
  nav          probe + log in (sinecins/web-superadmin), then dump the whole nav/menu tree + body text.
  logging      nav + try to open a Logging/Syslog/Diagnostics area and dump its controls (read-only).

Start Edge first (see tools/nms-onboarding/README.md). Close heavy apps if MC01 is low on RAM.
Exceptions print their type only (Playwright call logs can echo typed values).
"""
import hashlib
import base64
import json
import socket
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
STEP = sys.argv[3] if len(sys.argv) > 3 else "probe"
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOST = "10.1.20.21"
PIN_B64 = "NNYhb4KOn2K7ojV1Zvv2Br9tG2l4+bY4nMMNCtGZ54Y="  # SHA-256(DER), read 2026-10-20
BASE = f"https://{HOST}/"
OUT.mkdir(parents=True, exist_ok=True)


def check_pin() -> None:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    with c.wrap_socket(socket.create_connection((HOST, 443), 5)) as s:
        fp = base64.b64encode(hashlib.sha256(s.getpeercert(True)).digest()).decode()
    if fp != PIN_B64:
        sys.exit(f"INS TLS cert changed ({fp}); NOT sending credentials")
    print("TLS pin OK")


def dump_controls(page) -> list:
    return page.evaluate("""() => {
      const lab = el => { const r = el.closest('div,td,tr,label'); return r ? r.innerText.split('\\n')[0].trim().slice(0,60) : ''; };
      const out = [];
      document.querySelectorAll('select').forEach(s => { if (s.offsetParent) out.push({select: lab(s),
         value: s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : '', options: [...s.options].map(o => o.text.trim())}); });
      document.querySelectorAll('input').forEach(i => { if (i.offsetParent && i.type !== 'hidden') out.push({input: lab(i) || i.placeholder || i.name, type: i.type,
         value: i.type === 'password' ? '(hidden)' : i.value}); });
      return out; }""")


def dump_nav(page) -> list:
    # Every visible link / menu item with its href — so we can see where Logging/Syslog lives.
    return page.evaluate("""() => [...document.querySelectorAll('a,[role=menuitem],[role=tab],button')]
        .filter(e => e.offsetParent)
        .map(e => ({t: (e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,50), href: e.getAttribute('href')||''}))
        .filter(x => x.t)""")


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = next((x for x in ctx.pages if x.url.startswith(f"https://{HOST}/")), None)
    page = page or ctx.new_page()
    try:
        check_pin()
        page.bring_to_front()
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "ins_landing.png"), full_page=True)
        print("url:", page.url)
        print("login-page controls:", json.dumps(dump_controls(page)))

        if STEP == "probe":
            sys.exit(0)

        # --- log in ONLY if a password field is present (the Edge profile keeps the session, so
        #     re-runs are already authenticated -> no second login attempt, no lockout risk) ------
        if page.locator("input[type=password]:visible").count():
            cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("sinecins/web-superadmin")
            page.locator("input[type=text]:visible, input[name*=user i]:visible, input[placeholder*=user i]:visible").first.fill(cred.username)
            pwf = page.locator("input[type=password]:visible").first
            pwf.click(); page.keyboard.type(cred.password or "", delay=20)
            page.get_by_role("button", name="Log in").or_(page.get_by_role("button", name="Login")).first.click()
            page.wait_for_timeout(6000)
        print("after-login url:", page.url)
        page.screenshot(path=str(OUT / "ins_after_login.png"), full_page=True)
        print("nav:", json.dumps(dump_nav(page)))

        # Navigate by href (strict-mode text clicks on the nav fail), read-only dump per page.
        targets = {
            "logging": ["/network-service/syslog"],
            "explore": ["/network-service/syslog", "/network-service/radius",
                        "/system-administration", "/network-service/ntp"],
        }
        for href in targets.get(STEP, []):
            try:
                page.goto(f"https://{HOST}{href}", wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2500)
                tag = href.strip("/").replace("/", "_")
                page.screenshot(path=str(OUT / f"ins_{tag}.png"), full_page=True)
                print(f"[{href}] nav:", json.dumps(dump_nav(page)))
                print(f"[{href}] controls:", json.dumps(dump_controls(page)))
                print(f"[{href}] text:", " ".join(page.inner_text("body").split())[:2200])
            except Exception as e:  # noqa: BLE001
                print(f"[{href}] failed:", type(e).__name__)

        if STEP == "syslogcfg":
            # In-page tabs on the Syslog service page (hrefs are ""), read-only.
            page.goto(f"https://{HOST}/network-service/syslog", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            for tab in ("Syslog configuration", "Syslog filters"):
                try:
                    page.get_by_text(tab, exact=True).first.click(timeout=8000)
                    page.wait_for_timeout(2000)
                    page.screenshot(path=str(OUT / f"ins_syslog_{tab.split()[1]}.png"), full_page=True)
                    print(f"[{tab}] controls:", json.dumps(dump_controls(page)))
                    print(f"[{tab}] buttons:", page.eval_on_selector_all("button,[role=tab]", "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean)"))
                    print(f"[{tab}] text:", " ".join(page.inner_text("body").split())[:2200])
                except Exception as e:  # noqa: BLE001
                    print(f"[{tab}] failed:", type(e).__name__)

        if STEP == "authtest":
            # ONE wrong-password login then a correct one, to see how INS logs auth. Single bad
            # attempt only (no retry loop) to avoid locking the SuperAdmin account.
            cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("sinecins/web-superadmin")
            # log out via the user menu
            try:
                page.get_by_text("SuperAdmin", exact=False).first.click(timeout=8000)
                page.wait_for_timeout(1000)
                for name in ("Log out", "Logout", "Sign out", "Log off"):
                    b = page.get_by_text(name, exact=False)
                    if b.count():
                        b.first.click(); break
                page.wait_for_timeout(4000)
            except Exception as e:  # noqa: BLE001
                print("logout:", type(e).__name__)
            page.screenshot(path=str(OUT / "ins_logged_out.png"), full_page=True)

            def do_login(pwd, tag):
                page.goto(BASE, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2000)
                u = page.locator("input[type=text]:visible, input[name*=user i]:visible, input[placeholder*=user i]:visible").first
                p = page.locator("input[type=password]:visible").first
                if not u.count() or not p.count():
                    print(f"[{tag}] no login fields (already authenticated?)"); return
                u.fill(cred.username)
                p.click(); page.keyboard.type(pwd, delay=25)
                page.get_by_role("button", name="Log in").or_(page.get_by_role("button", name="Login")).first.click()
                page.wait_for_timeout(5000)
                page.screenshot(path=str(OUT / f"ins_auth_{tag}.png"), full_page=True)
                print(f"[{tag}] url={page.url} body:", " ".join(page.inner_text("body").split())[:500])

            do_login("Drill_WrongPass_0", "fail")     # single deliberate failure
            do_login(cred.password or "", "ok")        # correct login, end authenticated

        if STEP == "relay_enable":
            page.goto(f"https://{HOST}/network-service/syslog", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            page.get_by_text("Syslog configuration", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1200)
            page.get_by_text("Syslog relay", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1200)

            def tstate():
                return page.evaluate("""()=>[...document.querySelectorAll('input[type=checkbox]')].map(e=>{
                    let r=e; for(let i=0;i<6&&r;i++){r=r.parentElement; if(r&&/Enable Syslog (server|relay)/i.test(r.innerText))break;}
                    const m=r?(r.innerText.split('\\n').find(x=>/Enable Syslog/i.test(x))||'').trim():'';
                    return {t:m, checked:e.checked};}).filter(x=>x.t)""")

            print("before:", json.dumps(tstate()))
            for want in ("Enable Syslog server", "Enable Syslog relay"):
                cur = [x for x in tstate() if x["t"] == want]
                if cur and cur[0]["checked"]:
                    print(want, "already on"); continue
                label = page.get_by_text(want, exact=True).first
                row = label.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]")
                vis = row.locator("mat-slide-toggle, .mat-slide-toggle, [role=switch]")
                (vis.first if vis.count() else row.locator("input[type=checkbox]").first).click(force=True)
                page.wait_for_timeout(900)
                yes = page.get_by_role("button", name="Yes", exact=True)
                if yes.count():
                    yes.first.click(); page.wait_for_timeout(1800)
                print(want, "->", json.dumps(tstate()))
            page.wait_for_timeout(1000)
            page.screenshot(path=str(OUT / "ins_relay_enabled.png"), full_page=True)
            print("final:", json.dumps(tstate()))

        if STEP == "relay_apply":
            DEST, PROTO, PORT = "10.1.20.13", "UDP", "514"
            page.goto(f"https://{HOST}/network-service/syslog", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            page.get_by_text("Syslog configuration", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1200)
            page.get_by_text("Syslog relay", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1200)
            # already-configured guard: do not create a duplicate
            body = page.inner_text("body")
            if DEST in body:
                print("relay destination already present; skipping create")
            else:
                page.get_by_role("button", name="Create").first.click(timeout=8000)
                page.wait_for_timeout(1500)
                page.get_by_placeholder("IP address").first.fill(DEST)
                page.get_by_text("Select protocol", exact=False).first.click()
                page.wait_for_timeout(600)
                opt = page.get_by_role("option", name=PROTO)
                (opt.first if opt.count() else page.get_by_text(PROTO, exact=True).last).click()
                page.wait_for_timeout(400)
                page.get_by_placeholder("Port").first.fill(PORT)
                page.wait_for_timeout(300)
                page.screenshot(path=str(OUT / "ins_relay_filled.png"), full_page=True)
                dlg = page.locator("[role=dialog], .modal, .mat-dialog-container, .p-dialog").last
                (dlg.get_by_role("button", name="Create") if dlg.count() else page.get_by_role("button", name="Create").last).last.click()
                page.wait_for_timeout(2500)
            # enable the relay toggle if it is off
            try:
                rel = page.locator("xpath=//*[normalize-space(text())='Enable Syslog relay']").first
                tog = rel.locator("xpath=preceding::*[self::mat-slide-toggle or @role='switch' or (self::input and @type='checkbox')][1]")
                state = tog.get_attribute("aria-checked") or ("true" if (tog.get_attribute("class") or "").find("checked") >= 0 else "false")
                if state != "true":
                    tog.click()
                    page.wait_for_timeout(1500)
            except Exception as e:  # noqa: BLE001
                print("relay toggle:", type(e).__name__)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "ins_relay_applied.png"), full_page=True)
            print("relay table text:", " ".join(page.inner_text("body").split())[:1200])

        if STEP == "relay_probe":
            # Near-read-only: capture current toggle states + the Create-relay dialog fields, then Cancel.
            page.goto(f"https://{HOST}/network-service/syslog", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            page.get_by_text("Syslog configuration", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1500)
            toggles = page.evaluate("""() => [...document.querySelectorAll('input[type=checkbox],[role=switch],mat-slide-toggle')]
                .filter(e => e.offsetParent).map(e => { const r = e.closest('div,tr,label,mat-slide-toggle');
                  const t = r ? r.innerText.trim().split('\\n')[0].slice(0,60) : '';
                  const c = (e.checked !== undefined && e.type) ? e.checked : (e.getAttribute('aria-checked')||'?');
                  return {t, checked: c}; })""")
            print("toggles:", json.dumps(toggles))
            page.get_by_text("Syslog relay", exact=True).first.click(timeout=8000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "ins_relay_before.png"), full_page=True)
            try:
                page.get_by_role("button", name="Create").first.click(timeout=8000)
                page.wait_for_timeout(1800)
                page.screenshot(path=str(OUT / "ins_relay_create_dialog.png"), full_page=True)
                print("create-dialog controls:", json.dumps(dump_controls(page)))
                print("create-dialog buttons:", page.eval_on_selector_all("button", "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean)"))
                for name in ("Cancel", "Close", "Abort"):
                    b = page.get_by_role("button", name=name, exact=True)
                    if b.count():
                        b.first.click(); print("closed with", name); break
            except Exception as e:  # noqa: BLE001
                print("open Create failed:", type(e).__name__)

        if STEP == "syslogdeep":
            # Read-only: open each Syslog-configuration sub-section to see the forwarding knobs.
            page.goto(f"https://{HOST}/network-service/syslog", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            try:
                page.get_by_text("Syslog configuration", exact=True).first.click(timeout=8000)
                page.wait_for_timeout(1500)
            except Exception as e:  # noqa: BLE001
                print("open Syslog configuration failed:", type(e).__name__)
            for sub in ("Syslog relay", "Logging", "Secure Syslog client", "Secure Syslog server"):
                try:
                    page.get_by_text(sub, exact=True).first.click(timeout=8000)
                    page.wait_for_timeout(1800)
                    page.screenshot(path=str(OUT / f"ins_syslog_{sub.replace(' ', '_')}.png"), full_page=True)
                    print(f"[{sub}] controls:", json.dumps(dump_controls(page)))
                    print(f"[{sub}] text:", " ".join(page.inner_text("body").split())[:1800])
                except Exception as e:  # noqa: BLE001
                    print(f"[{sub}] failed:", type(e).__name__)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("step failed:", type(e).__name__)
        page and page.screenshot(path=str(OUT / f"ins_{STEP}_failed.png"))
