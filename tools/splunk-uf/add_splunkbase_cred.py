"""Add or update the `splunkbase/account` entry in the credentials file (values from env vars
SB_USER / SB_PASS, never printed), then confirm the app's CredentialStore loads it.
usage: python -I tools/splunk-uf/add_splunkbase_cred.py <backend_dir> <credentials.yaml>"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from app.core.credentials import CredentialStore  # noqa: E402

p = Path(sys.argv[2])
user, pw = os.environ.get("SB_USER", ""), os.environ.get("SB_PASS", "")
if not user or not pw:
    sys.exit("SB_USER / SB_PASS not set")
text = p.read_text(encoding="utf-8-sig")
entry = (
    "  splunkbase/account:                    # https://splunkbase.splunk.com\n"
    f"    username: {json.dumps(user)}\n"
    f"    password: {json.dumps(pw)}\n"
)
m = re.search(r"(?m)^  splunkbase/account:.*\n(?:    .*\n)*", text)
if m:
    text, how = text[:m.start()] + entry + text[m.end():], "updated"
else:
    text = text.rstrip("\n") + "\n  # splunk.com account for Splunkbase app downloads (operator, 2026-10-16).\n" + entry
    how = "added"
p.write_text(text, encoding="utf-8")
c = CredentialStore.load(p).credential("splunkbase/account")
print(f"{how}; CredentialStore reads username={c.username!r}, password set={bool(c.password)} "
      f"(length {len(c.password)})")
