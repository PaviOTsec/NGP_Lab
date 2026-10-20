from playwright.sync_api import sync_playwright
OPB = "https://192.168.30.11:8443/sinecnmsWebappControl/UI/#/"
OUT = r"C:\Users\Administrator\AppData\Local\LabConsole\nms-onboarding\20261012-phase4"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    op = next(x for x in b.contexts[0].pages if x.url.startswith("https://192.168.30.11:8443"))
    op.bring_to_front()
    op.goto(OPB + "network-monitoring/opMon/devices", wait_until="networkidle"); op.wait_for_timeout(6000)
    op.screenshot(path=OUT + r"\nms_op_devices_v3only.png", full_page=True)
    t = " ".join(op.inner_text("body").split())
    i = t.find("Event status"); print("events:", t[i:i+900])
