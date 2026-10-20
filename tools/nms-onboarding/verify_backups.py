"""Verify backups: non-empty, device identity inside, zips valid; write MANIFEST.json.
usage: python verify_backups.py <backup_dir> [device ...]   (default: the phase-3 NMS set)"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(sys.argv[1])
ALL_IPS = {"SW-WAN": "10.5.20.30", "SW-Ent": "10.4.20.30", "SW-DMZ": "10.1.20.30", "SW-Ops": "192.168.30.30",
           "OT-FW": "192.168.20.254", "FW-North": "10.4.20.254", "FW-South": "10.1.20.254",
           "SW-Mgmt": "192.168.100.30",
           # L2/L1 switches: rule-13 exception 2026-10-19 (syslog only); never in the default set
           "SW-L2": "192.168.20.50", "SW-PCS": "192.168.1.30", "SW-SIS": "192.168.2.30", "SW-SAS": "192.168.3.30"}
DEFAULT = ["SW-WAN", "SW-Ent", "SW-DMZ", "SW-Ops", "OT-FW", "FW-North", "FW-South"]
IPS = {k: ALL_IPS[k] for k in (sys.argv[2:] or DEFAULT)}
manifest, problems = {}, []
for dev, ip in IPS.items():
    d = ROOT / dev
    files = sorted(p for p in d.glob("*") if p.is_file() and not p.name.endswith(".raw") and p.name != "manifest.json")
    if not files:
        problems.append(f"{dev}: no files")
    for f in files:
        data = f.read_bytes()
        info = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if not data:
            problems.append(f"{dev}/{f.name}: empty")
        if f.suffix == ".zip":
            try:
                with zipfile.ZipFile(f) as z:
                    bad = z.testzip()
                    info["zip_entries"] = z.namelist()
                    if bad:
                        problems.append(f"{dev}/{f.name}: corrupt member {bad}")
            except zipfile.BadZipFile:
                problems.append(f"{dev}/{f.name}: not a zip")
        elif f.suffix in (".conf", ".txt", ".xml") and "config" in f.name.lower():
            info["contains_device_ip"] = ip.encode() in data
            if not info["contains_device_ip"]:
                problems.append(f"{dev}/{f.name}: device IP {ip} not found inside")
        manifest[f"{dev}/{f.name}"] = info
(ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
for k, v in manifest.items():
    extra = f" zip[{len(v['zip_entries'])}]" if "zip_entries" in v else (
        f" ip={'yes' if v.get('contains_device_ip') else 'NO'}" if "contains_device_ip" in v else "")
    print(f"{k:58} {v['bytes']:>9} {v['sha256'][:12]}{extra}")
print("PROBLEMS:" if problems else "ALL CHECKS PASSED", *problems, sep="\n  ")
