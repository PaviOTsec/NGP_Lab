"""Read-only: GET a KV store collection's records from DMZH1_SIEM (TLS pin checked before the credential).
usage: python -I -X utf8 tools/splunk-uf/kv_get.py <backend_dir> <app> <collection> [field,field,...]"""
import base64
import hashlib
import http.client
import json
import ssl
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.core.credentials import CredentialStore  # noqa: E402
from splunk_search import CERT_PIN, HOST, PORT  # noqa: E402

app, coll = sys.argv[2], sys.argv[3]
fields = sys.argv[4].split(",") if len(sys.argv) > 4 else None
cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("splunk/admin")
ctx = ssl.create_default_context()
ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
conn = http.client.HTTPSConnection(HOST, PORT, context=ctx, timeout=120)
conn.connect()
if hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest().upper() != CERT_PIN:
    raise SystemExit("TLS pin mismatch; no credential sent")
auth = base64.b64encode(f"{cred.username}:{cred.password}".encode()).decode()
conn.request("GET", f"/servicesNS/nobody/{app}/storage/collections/data/{coll}?output_mode=json",
             headers={"Authorization": "Basic " + auth})
r = conn.getresponse()
data = json.loads(r.read().decode("utf-8", "replace") or "[]")
if r.status != 200:
    raise SystemExit(f"HTTP {r.status}: {str(data)[:300]}")
print(f"{len(data)} record(s)")
# optional 5th arg: field!=value to hide records (e.g. status!=searching)
if len(sys.argv) > 5 and "!=" in sys.argv[5]:
    fk, fv = sys.argv[5].split("!=", 1)
    data = [r for r in data if str(r.get(fk)) != fv]
    print(f"{len(data)} with {fk} != {fv}")
for rec in data:
    print(json.dumps({k: rec.get(k) for k in fields} if fields else rec, ensure_ascii=False)[:400])
