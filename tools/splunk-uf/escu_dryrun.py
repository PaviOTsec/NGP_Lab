"""Read-only: dry-run ESCU detections against the lab data (in the ESCU app namespace) to see
which would fire and how often, before enabling them.

usage: python -I -X utf8 -W ignore tools/splunk-uf/escu_dryrun.py <backend_dir> <escu.tgz> <names-file> [earliest=-24h]
       names-file: one "ESCU - ... - Rule" saved-search name per line (escu_select.py ... names)
"""
import re
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splunk_search  # noqa: E402  (reads argv[1] = backend dir)

ESCU, NAMES = sys.argv[2], Path(sys.argv[3])
EARLIEST = sys.argv[4] if len(sys.argv) > 4 else "-24h"

with tarfile.open(ESCU, "r:*") as tf:
    conf = tf.extractfile("DA-ESS-ContentUpdate/default/savedsearches.conf").read().decode("utf-8", "replace")
searches = {}
for block in re.split(r"(?m)^\[", conf)[1:]:
    name, _, body = block.partition("]\n")
    m = re.search(r"(?ms)^search = (.*?)(?<!\\)\n(?=[\w.\-]+ = |\Z)", body)
    if m:
        searches[name] = re.sub(r"\\\n", "\n", m.group(1)).strip()

for name in [n.strip() for n in NAMES.read_text(encoding="utf-8-sig").splitlines() if n.strip()]:
    spl = searches.get(name)
    if not spl:
        print(f"   ?    {name}: not in ESCU savedsearches.conf")
        continue
    try:
        rows = splunk_search.search(spl, EARLIEST, "now", app="DA-ESS-ContentUpdate")
        print(f"   {len(rows):>4}  {name}")
        for r in rows[:2]:
            print("          " + ", ".join(f"{k}={str(v)[:70]}" for k, v in r.items()
                                        if not k.startswith("_") and v not in ("", None))[:400])
    except SystemExit as exc:
        print(f"   ERR   {name}: {str(exc)[:300]}")
