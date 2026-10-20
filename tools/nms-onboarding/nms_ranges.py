"""Edit NMS scan ranges in one dialog session, then save only if the enabled set == expected.

usage: python -I nms_ranges.py <ops...> -- <expected...>
  op   create:NAME:FIRST:LAST            new single range, enabled (names: no spaces)
       edit:OLDFIRST:FIRST:LAST          narrow an existing (e.g. disabled /24) range, enable it
  expected  NAME=FIRST-LAST  (the complete set of ranges that must be Enabled after the ops)
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "https://192.168.30.11/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase6"
OPS = BASE + "system-administration/operation-connectivity-management/operation-management"
sep = sys.argv.index("--")
ops, expected = sys.argv[1:sep], dict(a.split("=", 1) for a in sys.argv[sep + 1:])
RANGES = """() => Object.fromEntries([...document.querySelectorAll('div[role=row]')]
    .map(r => [r.querySelector('[col-id=firstIP]'), r.querySelector('[col-id=lastIP]'), r.querySelector('[col-id=customStatus]'), r.querySelector('[col-id=subgroupName]')])
    .filter(([f]) => f && /\\d+\\.\\d+/.test(f.innerText))
    .map(([f, l, s, n]) => [n.innerText.trim(), s.innerText.trim() + ' ' + f.innerText.trim() + '-' + l.innerText.trim()]))"""


def typ(pg, sel, val):
    f = pg.locator(sel); f.click(); f.press("Control+a"); f.press("Delete"); pg.keyboard.type(val, delay=25); pg.keyboard.press("Tab")


def fill(pg, first, last):
    typ(pg, "#sa_ocm_scanRangeEditorFirstIp", first)
    typ(pg, "#sa_ocm_scanRangeEditorLastIp", last)
    en = pg.locator("#sa_ocm_scanRangeEnable")
    if not en.is_checked():
        en.check(force=True)
    sel = pg.locator("#sa_ocm_scanRangeSelectOperation")
    if sel.count() and sel.first.is_enabled():
        sel.first.select_option(label="DMZH2Maint")
    pg.wait_for_timeout(1000)
    done = pg.locator("#sa_ocm_scanRangeDoneBtn")
    if not done.is_enabled():
        raise SystemExit(f"range form invalid for {first}-{last} (overlap?) â€” nothing saved")
    done.click(); pg.wait_for_timeout(2000)


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11/"))
    pg.bring_to_front()
    pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    print("before:", pg.evaluate(RANGES))
    try:
        for op in ops:
            kind, *a = op.split(":")
            if kind == "create":
                name, first, last = a
                pg.get_by_text("Create", exact=True).last.click(); pg.wait_for_timeout(2000)
                typ(pg, "#sa_ocm_scanRangeEditorRangeName", name)
                fill(pg, first, last)
            elif kind == "edit":
                old, first, last = a
                box = pg.locator(f"div[role=row]:has([col-id=firstIP] span:text-is('{old}')) [col-id=action] input[type=checkbox]")
                assert box.count() == 1, f"range starting {old} not found"
                box.first.check(force=True); pg.wait_for_timeout(500)
                pg.get_by_text("Edit", exact=True).last.click(); pg.wait_for_timeout(2000)
                fill(pg, first, last)
                box = pg.locator("div[role=row] [col-id=action] input[type=checkbox]:checked")
                for i in range(box.count()):
                    box.nth(i).uncheck(force=True)
        got = pg.evaluate(RANGES)
        enabled = {k: v.split(" ", 1)[1] for k, v in got.items() if v.startswith("Enabled")}
        print("unsaved:", got)
        if enabled != expected:
            raise SystemExit(f"enabled {enabled} != expected {expected}")
        pg.locator("#sa_ocm_ipScanRangeBaseSaveButton").click(); pg.wait_for_timeout(4000)
        print("saved")
    except SystemExit as e:
        print("ABORT:", e, "-> Cancel")
        pg.locator("#sa_ocm_scanRangeCancelBtn").click() if pg.locator("#sa_ocm_scanRangeCancelBtn").is_visible() else None
        pg.locator("#sa_ocm_ipScanRangeBaseCancelButton").click()
        sys.exit(1)
    pg.goto(OPS, wait_until="networkidle"); pg.wait_for_timeout(3000)
    pg.get_by_text("Edit scan ranges", exact=True).click(); pg.wait_for_timeout(3000)
    print("re-read:", pg.evaluate(RANGES))
    pg.screenshot(path=OUT + r"\nms_ranges_after.png", full_page=True)
    pg.locator("#sa_ocm_ipScanRangeBaseCancelButton").click()

