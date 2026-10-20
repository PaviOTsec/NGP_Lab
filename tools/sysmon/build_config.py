"""Build the lab Sysmon config: sysmon-modular "Balanced" with FULL process-creation logging.

usage: python -I -X utf8 tools/sysmon/build_config.py

Why (2026-10-16): Balanced only logs ProcessCreate for an include list (436 rules), so e.g.
setspn.exe was never logged and the ESCU Endpoint.Processes detections (which assume every process
start is recorded, like an EDR) could not fire. This keeps Balanced for every other event type,
drops its ProcessCreate *include* group (keeping the 178-rule exclude group - identical to the
release's excludes-only profile), and adds exclusions for Splunk's own helpers: their process
starts when splunkd.exe is the parent (every 30 s on every forwarder), and their DLL loads
(event 7, exact helper paths).
Inputs are the pinned release files (sha256 checked); output sysmonconfig-lab.xml + .sha256.
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "incoming" / "sysmonconfig-15.21.xml"
SRC_SHA = "64bec37ba849c5f2934a55d2a29e7ddfae46a30d56f7f2908d1f8a454898797e"
OUT = HERE / "sysmonconfig-lab.xml"

data = SRC.read_bytes()
if hashlib.sha256(data).hexdigest() != SRC_SHA:
    sys.exit("source config sha256 mismatch")
text = data.decode("utf-8-sig")

# Remove the ProcessCreate include group (the RuleGroup whose ProcessCreate has onmatch="include").
groups = list(re.finditer(r"(?s)<RuleGroup\b[^>]*>\s*<ProcessCreate onmatch=\"(include|exclude)\">.*?</ProcessCreate>\s*</RuleGroup>", text))
inc = [g for g in groups if g.group(1) == "include"]
exc = [g for g in groups if g.group(1) == "exclude"]
if len(inc) != 1 or len(exc) != 1:
    sys.exit(f"expected 1 include + 1 exclude ProcessCreate group, found {len(inc)} + {len(exc)}")
text = text[:inc[0].start()] + text[inc[0].end():]

LAB_RULES = """
      <!-- Lab Console 2026-10-16: Splunk's own helper processes, only when spawned by splunkd -->
      <Rule name="lab_splunk_uf_helpers" groupRelation="and">
        <ParentImage condition="is">C:\\Program Files\\SplunkUniversalForwarder\\bin\\splunkd.exe</ParentImage>
        <Image condition="begin with">C:\\Program Files\\SplunkUniversalForwarder\\bin\\splunk-</Image>
      </Rule>
      <Rule name="lab_splunk_enterprise_helpers" groupRelation="and">
        <ParentImage condition="is">C:\\Program Files\\Splunk\\bin\\splunkd.exe</ParentImage>
        <Image condition="begin with">C:\\Program Files\\Splunk\\bin\\splunk-</Image>
      </Rule>
    """
text = re.sub(r"(<ProcessCreate onmatch=\"exclude\">)", r"\1" + LAB_RULES.replace("\\", "\\\\"), text, count=1)

# ImageLoad (event 7): Splunk's helper processes load their DLLs on every (frequent) start -
# 3,534 events / 20 min from splunk-optimize.exe alone on the SIEM. Exact paths only.
HELPERS = ["splunk-optimize.exe", "splunk-powershell.exe", "splunk-MonitorNoHandle.exe", "splunk-admon.exe",
           "splunk-netmon.exe", "splunk-regmon.exe", "splunk-winevtlog.exe", "splunk-winprintmon.exe",
           "splunk-winhostinfo.exe", "splunk-perfmon.exe", "splunk-wmi.exe"]
DIRS = [r"C:\Program Files\Splunk\bin", r"C:\Program Files\SplunkUniversalForwarder\bin"]
IMG = "\n      <!-- Lab Console 2026-10-16: Splunk helper DLL loads (exact paths) -->\n" + "".join(
    f'      <Image condition="is">{d}\\{h}</Image>\n' for d in DIRS for h in HELPERS)
if text.count('<ImageLoad onmatch="exclude">') < 1:
    sys.exit("no ImageLoad exclude group found")
text = text.replace('<ImageLoad onmatch="exclude">', '<ImageLoad onmatch="exclude">' + IMG, 1)
text = text.replace("<Sysmon ", "<!-- Lab build: sysmon-modular configs-a45dedb13a43 Balanced 15.21, ProcessCreate = log all "
                    "minus excludes (tools/sysmon/build_config.py) -->\n<Sysmon ", 1)
out = text.encode("utf-8")
OUT.write_bytes(out)
sha = hashlib.sha256(out).hexdigest()
(OUT.parent / (OUT.name + ".sha256")).write_text(sha + "\n", encoding="ascii")
pc = re.findall(r"<ProcessCreate onmatch=\"(\w+)\"", text)
print(f"wrote {OUT.name} ({len(out):,} bytes) sha256 {sha}; ProcessCreate groups now: {pc}")
