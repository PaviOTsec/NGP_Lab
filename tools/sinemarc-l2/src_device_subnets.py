"""SINEMA RC: export L2/L1 subnets behind the OT firewall (device `Scalace_firewall`, id 2).

Operator request 2026-10-21 (rule-13 override): the SINEMA RC user `student` (member of
vpn_device_group, which has "All access" on the device) must reach L2 and below via the VPN only.

Target network settings (Remote connections > Devices > Scalace_firewall > Network Settings):
  "Device is a network gateway" OFF -> SINEMA RC forces source NAT on the device, so L1/L2 nodes
      reply to the firewall's own interface address whatever their gateway is (L2 uses .253).
  L2_Plant 192.168.20.0/24  1:1 NAT -> 172.17.20.0/24  (the device's tunnel originates from
      192.168.20.254, so the real subnet must not be routed into the tunnel on the server)
  L1_PCS 192.168.1.0/24, L1_SIS 192.168.2.0/24, L1_SAS 192.168.3.0/24, L1_Net4 192.168.4.0/24  no NAT
  every subnet: participant group vpn_device_group; no port groups (full IP access, operator).
  192.168.12.0/24 (routed via 192.168.2.10) deliberately left out (operator).

usage: python -I src_device_subnets.py <backend_dir> <out_dir> stage|save|remove
  stage  : precheck that the device still has the recorded pre-change settings, fill the form via
           the page's own loader, read the form back, screenshot. Nothing is saved.
  save   : stage + press Save, reload, compare what the server stored with the target.
  remove : rollback - restore the pre-change settings (no subnets, gateway ON) and verify.
Requires a session from `src_wbm.py ... login` in the operator-visible Edge (CDP :9222).
"""
import json
import sys
import time
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
MODE = sys.argv[3]
assert MODE in ("stage", "save", "remove")
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

URL = "https://10.1.20.16/wbm/device/2/network_settings/"
GROUP = "vpn_device_group"
BEFORE = {"default_gateway": "True", "subnets": []}


def subnet(name: str, ip: str, nat: int = 0, vip: str = "") -> dict:
    return {"subnet_name": name, "subnet_access_groups": [GROUP], "subnet_ip": ip,
            "subnet_mask": "255.255.255.0", "nat_mode": nat, "virtual_subnet_ip": vip,
            "virtual_subnet_mask": "255.255.255.0" if nat else "", "nodes": [], "subnet_portgroups": []}


TARGET = {"default_gateway": "False", "subnets": [
    subnet("L2_Plant", "192.168.20.0", 2, "172.17.20.0"),
    subnet("L1_PCS", "192.168.1.0"),
    subnet("L1_SIS", "192.168.2.0"),
    subnet("L1_SAS", "192.168.3.0"),
    subnet("L1_Net4", "192.168.4.0"),
]}
KEYS = ("subnet_name", "subnet_access_groups", "subnet_ip", "subnet_mask", "nat_mode", "virtual_subnet_ip")


def norm(s: dict) -> dict:
    return {"default_gateway": str(s.get("default_gateway")),
            "subnets": sorted(({k: x.get(k) for k in KEYS} | {"nodes": len(x.get("nodes") or []),
                                "portgroups": len(x.get("subnet_portgroups") or [])}
                               for x in s.get("subnets") or []), key=lambda x: x["subnet_name"])}


def server_state(page) -> dict:  # what the server rendered into the page on load
    return json.loads(page.evaluate("() => device_network_settings"))


def form_state(page) -> dict:  # what Save would submit
    return page.evaluate("() => generateNetworkSettingsJSON()")


def shot(page, tag: str) -> None:
    page.screenshot(path=str(OUT / f"src_{time.strftime('%H%M%S')}_netsettings_{tag}.png"), full_page=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    want, expect_now = (BEFORE, TARGET) if MODE == "remove" else (TARGET, BEFORE)
    audit = AuditLog(Settings.load().audit_abs)
    with sync_playwright() as pw:
        page = None
        for ctx in pw.chromium.connect_over_cdp("http://127.0.0.1:9222").contexts:
            page = next((p for p in ctx.pages if p.url.startswith("https://10.1.20.16")), page)
        if page is None:
            sys.exit("no SINEMA RC tab; run src_wbm.py login first")
        page.bring_to_front()
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            sys.exit("session expired; run src_wbm.py login")
        now = server_state(page)
        print("server now :", json.dumps(norm(now)))
        if norm(now) != norm(expect_now):
            sys.exit("PRECHECK FAILED: device settings differ from the recorded state; nothing changed")
        shot(page, f"{MODE}-before")
        if MODE == "remove":
            page.evaluate("() => $('#subnets').find('.delete-section-part').trigger('click')")
        page.evaluate("(j) => loadNetworkSettingsData(j, true)", json.dumps(want))
        form = form_state(page)
        print("form staged:", json.dumps(norm(form)))
        if norm(form) != norm(want):
            shot(page, f"{MODE}-mismatch")
            sys.exit("FORM MISMATCH after staging; not saving (reload the page to discard)")
        shot(page, f"{MODE}-staged")
        if MODE == "stage":
            print("STAGED ONLY - not saved. Reload the page to discard.")
            return 0
        page.click("#save")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        errors = page.evaluate("() => [...document.querySelectorAll('.errorlist, .error, .alert-danger')]"
                               ".map(e => e.innerText.trim()).filter(Boolean)")
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        stored = server_state(page)
        shot(page, f"{MODE}-after")
        ok = norm(stored) == norm(want)
        print("server after:", json.dumps(norm(stored)))
        if errors:
            print("page messages:", errors)
        audit.record(action=f"sinemarc.device-subnets.{MODE}", target="DMZH2_SinemaRC/device:Scalace_firewall",
                     transport="https-wbm", result="ok" if ok else "error",
                     detail={"want": norm(want), "stored": norm(stored)})
        print("RESULT", "OK" if ok else "MISMATCH")
        return 0 if ok else 1


sys.exit(main())
