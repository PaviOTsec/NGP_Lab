"""Read-only: choose which ESCU detections the lab can run, from the ESCU + Security Essentials packages.

usage: python -I -X utf8 tools/splunk-uf/escu_select.py <escu.tgz> <sse.tgz> [stories|pick N|names]

Keeps TTP detections whose searches only use data we collect: Windows event-log macros
(wineventlog_security / wineventlog_system / powershell), `sysmon`, or the Endpoint
(Processes/Registry/Filesystem), Authentication and Change data models.
`stories` = counts per analytic story; `pick N` = the N highest-severity detections from the
priority stories below (spread across them), printed as ESCU saved-search names.
"""
import collections
import json
import re
import sys
import tarfile

ESCU, SSE = sys.argv[1], sys.argv[2]
MODE = sys.argv[3] if len(sys.argv) > 3 else "stories"

with tarfile.open(ESCU, "r:*") as tf:
    conf = tf.extractfile("DA-ESS-ContentUpdate/default/savedsearches.conf").read().decode("utf-8", "replace")
with tarfile.open(SSE, "r:*") as tf:
    meta = json.load(tf.extractfile("Splunk_Security_Essentials/appserver/static/vendor/splunk/Splunk_Research_Detections.json"))
meta = meta if isinstance(meta, list) else meta.get("detections", meta)
by_name = {m["name"]: m for m in meta if isinstance(m, dict) and "name" in m}

stanzas = {}
for block in re.split(r"(?m)^\[", conf)[1:]:
    name, _, body = block.partition("]\n")
    stanzas[name] = body

LOG = {"wineventlog_security", "wineventlog_system", "powershell", "sysmon"}
DM_OK = re.compile(r"datamodel=(Endpoint\.(Processes|Registry|Filesystem)|Authentication(\.Authentication)?|Change(\.All_Changes)?)\b")
DM_ANY = re.compile(r"datamodel=([A-Za-z_]+(?:\.[A-Za-z_]+)?)")
SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1}
PRIORITY = ["Credential Dumping", "Ransomware", "Windows Defense Evasion Tactics", "Windows Persistence Techniques",
            "Windows Privilege Escalation", "Active Directory Lateral Movement", "Active Directory Kerberos Attacks",
            "Suspicious Command-Line Executions", "Living Off The Land", "Windows Log Manipulation",
            "Disabling Security Tools", "Windows Service Abuse", "Suspicious WMI Use", "Malicious PowerShell",
            "Windows Registry Abuse", "Industroyer2", "Data Destruction", "Active Directory Privilege Escalation"]


def usable(m) -> bool:
    s = m.get("search", "") or ""
    if m.get("type") != "TTP":
        return False
    first = re.search(r"`([a-z0-9_]+)`", s)
    dms = DM_ANY.findall(s)
    if dms:
        return all(DM_OK.match("datamodel=" + d) for d in dms)
    return bool(first) and first.group(1) in LOG


rows = []
for stanza in stanzas:
    m = re.match(r"ESCU - (.+) - Rule$", stanza)
    if not m or m.group(1) not in by_name:
        continue
    d = by_name[m.group(1)]
    if usable(d):
        rows.append((stanza, d))

if MODE == "stories":
    print(f"usable TTP detections: {len(rows)} (of {len(stanzas)} ESCU searches)")
    c = collections.Counter(s for _, d in rows for s in (d.get("tags", {}).get("analytic_story") or []))
    for s, n in c.most_common(40):
        print(f"  {n:4} {'*' if s in PRIORITY else ' '} {s}")
    print("by severity:", collections.Counter(d.get("risk_severity", "?") for _, d in rows).most_common())
elif MODE in ("pick", "names"):
    n = int(sys.argv[4]) if MODE == "pick" and len(sys.argv) > 4 else 50
    keep = [(st, d) for st, d in rows if "linux" not in st.lower()
            and d.get("risk_severity") not in ("low", "informational")]
    pools = {s: sorted([(st, d) for st, d in keep if s in (d.get("tags", {}).get("analytic_story") or [])],
                       key=lambda x: (-SEV.get(x[1].get("risk_severity", ""), 0), x[0])) for s in PRIORITY}
    chosen, seen = [], set()
    while len(chosen) < n and any(pools.values()):
        for s in PRIORITY:  # round-robin over the priority stories, best severity first
            while pools[s] and pools[s][0][0] in seen:
                pools[s].pop(0)
            if pools[s] and len(chosen) < n:
                st, d = pools[s].pop(0)
                seen.add(st)
                chosen.append((st, d, s))
    for st, d, s in chosen:
        mitre = ",".join(d.get("tags", {}).get("mitre_attack_id") or [])[:20]
        src = (re.search(r"`([a-z0-9_]+)`", d.get("search", "")) or [None, "?"])[1]
        dm = ",".join(sorted(set(DM_ANY.findall(d.get("search", ""))))) or src
        if MODE == "names":
            print(st)
        else:
            print(f"{d.get('risk_severity', '?'):8} {mitre:20} {dm[:26]:26} [{s[:24]}] {st}")
