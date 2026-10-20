"""Export PAN-OS configuration byte-exact via the XML API (read-only for the config).

keygen (POST, credentials in the body) -> export running config + the named snapshot.
TLS cert pinned (first contact recorded). The API key is never printed or saved.
usage: python -I pan_export.py <backend_dir> <out_dir> <snapshot-name>
"""
import hashlib
import json
import re
import socket
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
SNAP = sys.argv[3]
HOST = "10.1.20.254"
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
pins_file = OUT.parent / "tls_pins.json"
pins = json.loads(pins_file.read_text()) if pins_file.exists() else {}
with ctx.wrap_socket(socket.create_connection((HOST, 443), 5)) as s:
    fp = "SHA256:" + hashlib.sha256(s.getpeercert(True)).hexdigest().upper()
if HOST in pins and pins[HOST] != fp:
    sys.exit("TLS cert changed; not sending credentials")
pins[HOST] = fp
pins_file.write_text(json.dumps(pins, indent=1))
print("TLS pin", HOST, fp)


def api(params: dict, post: bool = False) -> bytes:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://{HOST}/api/", data=data if post else None,
                                 method="POST" if post else "GET")
    if not post:
        req.full_url = f"https://{HOST}/api/?" + data.decode()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        return r.read()


cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
resp = api({"type": "keygen", "user": cred.username, "password": cred.password or ""}, post=True).decode()
m = re.search(r"<key>(.+?)</key>", resp)
if not m:
    sys.exit("keygen failed: " + re.sub(r"<key>.*?</key>", "<key>…</key>", resp)[:200])
key = m.group(1)
out = OUT / "FW-South"
out.mkdir(parents=True, exist_ok=True)
for label, params in [("running-config.xml", {"type": "export", "category": "configuration"}),
                      (SNAP, {"type": "export", "category": "configuration", "from": SNAP})]:
    body = api({**params, "key": key})
    complete = body.lstrip().startswith(b"<config") and body.rstrip().endswith(b"</config>")
    ts = __import__("time").strftime("%Y%m%d-%H%M%S")
    (out / f"FW-South_{HOST}_{ts}_api_{label}").write_bytes(body)
    print(f"{label}: {len(body)} bytes, sha256 {hashlib.sha256(body).hexdigest()[:16]}…, complete={complete}")
pend = api({"type": "op", "cmd": "<check><pending-changes></pending-changes></check>", "key": key}).decode()
print("pending changes:", re.sub(r"\s+", " ", pend)[:200])
ts = __import__("time").strftime("%Y%m%d-%H%M%S")
(out / f"FW-South_{HOST}_{ts}_pending-changes.txt").write_text("check pending-changes (XML API, op): " + pend.strip(), encoding="utf-8")
