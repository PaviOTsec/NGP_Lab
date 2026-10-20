"""Check the LAB alerts on DMZH1_SIEM: loaded + scheduled, then each search run over a past window
(index-time window removed) to show syntax errors and how often it would have fired. Read-only.

usage: python -I -X utf8 -W ignore tools/splunk-uf/validate_alerts.py <backend-dir> [earliest=-30d]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splunk_search  # noqa: E402  (sets up the backend path from argv[1])

EARLIEST = sys.argv[2] if len(sys.argv) > 2 else "-30d"

saved = splunk_search.search(
    '| rest /servicesNS/-/lab_security/saved/searches splunk_server=local count=0 '
    '| search eai:acl.app=lab_security '
    '| table title search is_scheduled disabled cron_schedule next_scheduled_time alert.severity', "-1m", "now")
print(f"== {len(saved)} saved searches in lab_security")
for s in saved:
    print(f"   sched={s.get('is_scheduled')} disabled={s.get('disabled')} cron={s.get('cron_schedule'):<14} "
          f"next={s.get('next_scheduled_time', '')[:19]}  {s['title']}")

print(f"\n== dry run over {EARLIEST}..now (rows = results the alert would have produced)")
for s in saved:
    spl = re.sub(r"\s_index_(earliest|latest)=\S+", "", s["search"])
    try:
        rows = splunk_search.search(spl, EARLIEST, "now")
        print(f"   {len(rows):>4} rows  {s['title']}")
        for r in rows[:3]:
            print("          " + ", ".join(f"{k}={str(v)[:60]}" for k, v in r.items() if not k.startswith("_")))
    except SystemExit as exc:
        print(f"   ERROR  {s['title']}: {exc}")
