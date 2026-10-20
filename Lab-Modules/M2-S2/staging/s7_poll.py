#!/usr/bin/env python3
"""M2-S2 K1: the rogue S7 reader on the kit's Kali VM.

Read-only and rate-limited: every 20-40 s (about 10% of cycles skipped) it connects, reads the
CPU state and 4 bytes of MB0, then disconnects. It never writes.

DRAFT, untested. Needs python-snap7 (pip install python-snap7). Rack/slot for the CPU 410 are
placeholders until M2S2-Q4.
"""
import argparse
import random
import sys
import time
from datetime import datetime

import snap7


def poll_once(ip: str, rack: int, slot: int) -> str:
    client = snap7.client.Client()
    try:
        client.connect(ip, rack, slot)
        state = client.get_cpu_state()
        mb0 = client.mb_read(0, 4)
        return f"state={state} MB0..3={bytes(mb0).hex()}"
    finally:
        client.disconnect()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plc_ip")
    ap.add_argument("--rack", type=int, default=0)
    ap.add_argument("--slot", type=int, default=3)
    ap.add_argument("--min", dest="min_s", type=float, default=20.0)
    ap.add_argument("--max", dest="max_s", type=float, default=40.0)
    ap.add_argument("--skip", type=float, default=0.1, help="fraction of cycles skipped")
    args = ap.parse_args()

    while True:
        stamp = datetime.now().isoformat(timespec="seconds")
        if random.random() >= args.skip:
            try:
                print(f"{stamp} {poll_once(args.plc_ip, args.rack, args.slot)}", flush=True)
            except Exception as exc:  # keep polling; the CPU may be in STOP or restarting
                print(f"{stamp} error: {exc}", flush=True)
        else:
            print(f"{stamp} skipped", flush=True)
        time.sleep(random.uniform(args.min_s, args.max_s))


if __name__ == "__main__":
    sys.exit(main())
