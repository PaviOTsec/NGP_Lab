"""Generate the Splunk asset lookup (lab_security/lookups/lab_assets.csv) from config/inventory.yaml.

One row per identity KEY (IP address, Windows host name, inventory name, VM name - lower-cased), all
pointing at the same asset, so Zeek/Suricata IPs, Windows `host` values and network-device names
resolve to one asset with its zone, role, criticality and risk weight (used by the risk/correlation
searches). Rerun after inventory changes, then deploy_ds.py.

Weights (operator, 2026-10-21): L1 x3, L2/Plantbus x2 (by inventory segment, not by IP: L2-HOST-1 and
L2BM_BR sit on the 192.168.100 management network but are OT), DC / SIEM / hypervisors x1.5, else x1.

usage: python -I -X utf8 tools/splunk-uf/make_assets.py <backend_dir> [--check]
"""
import csv
import io
import ipaddress
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.models.inventory import Inventory, Segment, TargetKind  # noqa: E402

APP = Path(__file__).resolve().parent / "ds" / "apps" / "lab_security"
ZONES = APP / "lookups" / "lab_zones.csv"
OUT = APP / "lookups" / "lab_assets.csv"
COLUMNS = ["key", "asset", "hostname", "ip", "zone", "segment", "kind", "role", "criticality", "risk_weight", "ot"]
# first matching tag gives the role; otherwise the kind
ROLE_TAGS = ["dc", "siem", "logserver", "sinec-nms", "sinec-ins", "sinema-rc", "historian", "mail", "wsus", "epo",
             "attacker", "sis", "plc", "ied", "rtu", "io", "firewall", "switch", "wireless", "veeam", "pcs7"]


def zone_of(ip: str, zones: list[tuple[ipaddress.IPv4Network, str]]) -> str:
    if not ip:
        return ""
    addr = ipaddress.ip_address(ip)
    hits = [(net.prefixlen, z) for net, z in zones if addr in net]
    return max(hits)[1] if hits else "Other"


def classify(t) -> tuple[str, str, float]:
    tags = set(t.tags)
    role = next((r for r in ROLE_TAGS if r in tags), t.kind.value)
    if t.name.upper().endswith("ES01"):
        role = "engineering-station"
    elif role == "pcs7":
        role = "pcs7-os"  # OSS/OSC operator stations
    if t.segment == Segment.L1:
        crit, w = ("critical-safety" if "sis" in tags else "critical"), 3.0
    elif t.ot:
        crit, w = "high", 2.0
    elif tags & {"dc", "siem"} or t.kind == TargetKind.HYPERVISOR:
        crit, w = "high", 1.5
    else:
        crit, w = "normal", 1.0
    return role, crit, w


def main() -> None:
    inv = Inventory.load(Settings.load().inventory_path)
    zones = [(ipaddress.ip_network(r["subnet"]), r["zone"]) for r in csv.DictReader(ZONES.open(encoding="utf-8"))]
    rows, seen, clashes = [], {}, []
    for t in inv.all():
        role, crit, w = classify(t)
        base = {"asset": t.name, "hostname": t.expected_hostname, "ip": t.address, "zone": zone_of(t.address, zones),
                "segment": t.segment.value, "kind": t.kind.value, "role": role, "criticality": crit,
                "risk_weight": f"{w:g}", "ot": "true" if t.ot else "false"}
        for k in dict.fromkeys(x.strip().lower() for x in (t.address, t.expected_hostname, t.name, t.vm_name or "") if x):
            if k in seen and seen[k] != t.name:
                clashes.append(f"{k}: {seen[k]} vs {t.name} (kept {seen[k]})")
                continue
            seen[k] = t.name
            rows.append({"key": k, **base})
    buf = io.StringIO()
    wr = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    wr.writeheader()
    wr.writerows(sorted(rows, key=lambda r: (r["asset"].lower(), r["key"])))
    text = buf.getvalue()
    assets = {r["asset"] for r in rows}
    print(f"{len(assets)} assets, {len(rows)} keys; weights: "
          + ", ".join(f"x{w}={sum(1 for a in assets if next(r for r in rows if r['asset'] == a)['risk_weight'] == w)}"
                      for w in sorted({r['risk_weight'] for r in rows})))
    for c in clashes:
        print("  key clash:", c)
    if "--check" in sys.argv:
        print(text)
        return
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if old == text:
        print(f"{OUT.name} unchanged")
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")


main()
