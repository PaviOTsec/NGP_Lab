"""Read-only: summarise the Splunk research detections bundled in the Security Essentials package
and pick the ones our data can feed. Reads JSON out of the .tgz (never extracts).

usage: python -I -X utf8 tools/splunk-uf/sse_catalog.py <sse.tgz> [summary|list|show <name substring>]
"""
import collections
import json
import re
import sys
import tarfile

PKG, MODE = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "summary")
with tarfile.open(PKG, "r:*") as tf:
    raw = json.load(tf.extractfile("Splunk_Security_Essentials/appserver/static/vendor/splunk/Splunk_Research_Detections.json"))
dets = raw if isinstance(raw, list) else raw.get("detections", raw.get("data", list(raw.values())[0] if raw else []))
if isinstance(dets, dict):
    dets = list(dets.values())


def get(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return default


def sources(d) -> list[str]:
    s = get(d, "data_source", "data_sources", default=[]) or get(get(d, "tags", default={}) or {}, "data_source", default=[]) or []
    return [s] if isinstance(s, str) else list(s)


# Data we have: classic Windows event logs (Security, System, PowerShell Operational, Defender).
HAVE = re.compile(r"(?i)^windows event log (security|system|powershell|defender|application|directory service|dns server)|"
                  r"^powershell script block logging|^windows event log microsoft windows (powershell|windows defender)")
NEED_OFF = re.compile(r"(?i)sysmon|crowdstrike|edr|carbon|sentinel|o365|aws|azure|gcp|okta|zeek|suricata|"
                      r"palo alto|cisco|linux|osquery|kubernetes|github|nginx|apache")

LOG_MACROS = {"wineventlog_security", "wineventlog_system", "wineventlog_application", "powershell",
              "wineventlog_defender", "windows_defender", "wineventlog_dns", "wineventlog_ad"}
XML_FIELDS = re.compile(r"\b(TargetUserName|SubjectUserName|TargetDomainName|IpAddress|ObjectName|ObjectType|"
                        r"ServiceName|ImagePath|ScriptBlockText|AccessMask|ShareName|RelativeTargetName|"
                        r"TaskName|TaskContent|LogonType|Status|SubStatus|ProcessName|PrivilegeList|MemberSid|"
                        r"TargetSid|SamAccountName|AttributeLDAPDisplayName|Ticket_Encryption_Type|TicketEncryptionType)\b")


def first_macro(d) -> str:
    m = re.search(r"`([a-z0-9_]+)`", get(d, "search", default="") or "")
    return m.group(1) if m else ""


def models(d) -> set[str]:
    return set(re.findall(r"datamodel=([A-Za-z_]+(?:\.[A-Za-z_]+)?)", get(d, "search", default="") or ""))


def eventcodes(d) -> set[str]:
    s = get(d, "search", default="") or ""
    return set(re.findall(r"EventCode\s*=\s*\"?(\d{3,5})", s)) | {c for grp in re.findall(r"EventCode\s+IN\s*\(([^)]*)\)", s)
                                                                  for c in re.findall(r"\d{3,5}", grp)}


if MODE == "classify":
    prod = [d for d in dets if get(d, "type", default="") in ("TTP", "Anomaly")]
    print(f"TTP+Anomaly: {len(prod)} of {len(dets)}")
    print("first macro (top 20):", collections.Counter(first_macro(d) for d in prod).most_common(20))
    print("data models (top 12):", collections.Counter(m for d in prod for m in models(d)).most_common(12))
    logs = [d for d in prod if first_macro(d) in LOG_MACROS and not models(d)]
    print(f"\nevent-log detections (no data model): {len(logs)}")
    print("  by macro:", collections.Counter(first_macro(d) for d in logs).most_common())
    xml = [d for d in logs if XML_FIELDS.search(get(d, "search", default=""))]
    print(f"  of which use XML-rendered field names: {len(xml)}")
    print("  event codes used (top 30):", collections.Counter(c for d in logs for c in eventcodes(d)).most_common(30))
    sys.exit(0)

if MODE == "summary":
    print(f"detections: {len(dets)}; keys of first: {sorted(dets[0].keys())[:40]}")
    usable = [d for d in dets if sources(d) and all(HAVE.search(s) for s in sources(d))]
    print(f"usable with our data only: {len(usable)}")
    print("by type:", collections.Counter(get(d, "type", default="?") for d in usable).most_common())
    print("by status:", collections.Counter(get(d, "status", default="?") for d in usable).most_common())
    print("data sources:", collections.Counter(s for d in usable for s in sources(d)).most_common(25))
    print("all data sources (top 25):", collections.Counter(s for d in dets for s in sources(d)).most_common(25))
elif MODE == "list":
    for d in sorted((d for d in dets if sources(d) and all(HAVE.search(s) for s in sources(d))),
                    key=lambda d: (get(d, "type", default=""), get(d, "name", default=""))):
        mitre = get(get(d, "tags", default={}) or {}, "mitre_attack_id", default=[]) or []
        print(f"{get(d, 'type', default='?'):9} {get(d, 'status', default='?'):12} {','.join(mitre)[:22]:22} "
              f"{get(d, 'name', default='?')}  [{'; '.join(sources(d))}]")
elif MODE == "show":
    pat = sys.argv[3].lower()
    for d in dets:
        if pat in str(get(d, "name", default="")).lower():
            print(json.dumps({k: d.get(k) for k in ("name", "type", "status", "description", "search", "how_to_implement",
                                                    "known_false_positives", "data_source", "tags")}, indent=1)[:4000])
            print("-----")
