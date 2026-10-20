"""Build the M1-S1 synthetic rack capture.

Usage:
    .\tools\lab-pcap\.venv\Scripts\python.exe -I tools\lab-pcap\build.py
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from labpcap import spec as spec_mod
from labpcap.flows import Ctx
from labpcap.flows import s7, modbus, iec61850, profinet, background
from labpcap.timeline import Timeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(HERE / "spec" / "m1s1.yaml"))
    ap.add_argument("--only", help="comma-separated subset: s7,modbus,iec,profinet,background")
    args = ap.parse_args()

    spec = spec_mod.load(args.spec)
    duration = float(spec.capture["duration_s"])
    seed = int(spec.capture["seed"])
    rng = random.Random(seed)
    tl = Timeline(duration)
    ctx = Ctx(spec=spec, tl=tl, rng=rng)

    only = set((args.only or "s7,modbus,iec,profinet,background").split(","))

    if "profinet" in only:
        print("  * PROFINET + LLDP + DCP ...")
        profinet.generate(ctx)
    if "background" in only:
        print("  * background (NTP, DNS, SNMPv3, ARP) ...")
        background.generate(ctx)
    if "modbus" in only:
        print("  * Modbus/TCP + planted gateway ...")
        modbus.generate(ctx)
    if "iec" in only:
        print("  * IEC 61850 MMS + GOOSE ...")
        iec61850.generate(ctx)
    if "s7" in only:
        print("  * S7comm (OS cyclic + ES session) ...")
        s7.generate(ctx)

    out_dir = Path(spec.capture["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / spec.capture["name"]
    sha = tl.write(out_path, spec.start_epoch, spec.capture["interface"])
    print(f"\n[+] wrote {out_path}  ({out_path.stat().st_size:,} bytes, {len(tl.frames)} frames)")
    print(f"    SHA-256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
