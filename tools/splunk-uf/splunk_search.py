"""Run a read-only Splunk search on DMZH1_SIEM over REST (8089) and print the results.

The TLS certificate is checked against the pin BEFORE the credential is sent (CLAUDE.md rule 12);
the pin was read from $SPLUNK_HOME\\etc\\auth\\server.pem over identity-checked WinRM (2026-10-16).
Credential: `splunk/admin` from the credentials file (never printed).

usage: python -I -X utf8 tools/splunk-uf/splunk_search.py <backend-dir> "<spl>" [earliest] [latest]
       e.g. ... "index=wineventlog | stats count by host" -24h now
       or  ... @path\to\query.spl -7d     (search text read from a file)
       (the search may start with `|` for generating commands; otherwise `search ` is prefixed)
"""
import base64
import hashlib
import http.client
import json
import ssl
import sys
import urllib.parse
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

HOST, PORT = "10.1.20.15", 8089
CERT_PIN = "BDF7B6DFEF5B3E0293A7FBDBF53555C9404DEC4DB06DB1E27099900B56EA1CFB"


def search(spl: str, earliest: str = "-24h", latest: str = "now", app: str = "") -> list[dict]:
    """Oneshot search. `app` runs it in that app's namespace (its app-local macros/lookups)."""
    cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("splunk/admin")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed: verified by the pin below instead
    conn = http.client.HTTPSConnection(HOST, PORT, context=ctx, timeout=300)
    conn.connect()
    got = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest().upper()
    if got != CERT_PIN:
        conn.close()
        raise SystemExit(f"TLS pin mismatch on {HOST}:{PORT} ({got}); no credential sent")
    q = spl.strip()
    body = urllib.parse.urlencode({
        "search": q if q.startswith("|") else "search " + q, "exec_mode": "oneshot",
        "earliest_time": earliest, "latest_time": latest, "output_mode": "json", "count": 0})
    auth = base64.b64encode(f"{cred.username}:{cred.password}".encode()).decode()
    path = (f"/servicesNS/{urllib.parse.quote(cred.username)}/{urllib.parse.quote(app)}/search/jobs"
            if app else "/services/search/jobs")
    conn.request("POST", path, body=body, headers={
        "Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "replace")
    conn.close()
    if resp.status != 200:
        raise SystemExit(f"HTTP {resp.status}: {data[:500]}")
    out = json.loads(data)
    for m in out.get("messages", []):
        print(f"[{m.get('type')}] {m.get('text')}", file=sys.stderr)
    return out.get("results", [])


if __name__ == "__main__":
    # `@file.spl` reads the search from a file: Windows PowerShell 5.1 mangles embedded double
    # quotes in native-command arguments, which breaks most real SPL passed inline.
    spl = Path(sys.argv[2][1:]).read_text(encoding="utf-8-sig") if sys.argv[2].startswith("@") else sys.argv[2]
    rows = search(spl, *(sys.argv[3:5]))
    for r in rows:
        print(json.dumps({k: v for k, v in r.items() if not k.startswith("_") or k in ("_time", "_raw")},
                         ensure_ascii=False))
    print(f"-- {len(rows)} row(s)", file=sys.stderr)
