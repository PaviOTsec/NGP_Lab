"""Download pinned Splunkbase app releases to tools/splunk-uf/apps-incoming/ and inspect them.

Login: `splunkbase/account` from the credentials file (never printed) -> Splunkbase login API
-> auth token -> each release's download URL (normal certificate verification throughout).
Each archive is only READ (never extracted or executed here): rejected if any member path is
absolute or contains '..', or if there isn't exactly one top-level app folder; the app id and
version are taken from its app.conf and must match what was asked for.

usage: python -I -X utf8 tools/splunk-uf/splunkbase_fetch.py <backend_dir> [app ...]
       app = key from RELEASES (default: all)
"""
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

OUT = Path(__file__).resolve().parent / "apps-incoming"
# key: (splunkbase id, release, expected app folder) - versions checked for Splunk 10.6, 2026-10-16
RELEASES = {
    "windows": (742, "11.0.3", "Splunk_TA_windows"),
    "cim": (1621, "8.7.0", "Splunk_SA_CIM"),
    "sse": (3435, "3.8.3", "Splunk_Security_Essentials"),
    "sysmon": (5709, "5.0.1", "Splunk_TA_microsoft_sysmon"),
    "escu": (3449, "6.8.0", "DA-ESS-ContentUpdate"),
    # network-device syslog via Scribbler (docs/SPLUNK_SCRIBBLER_PLAN.md), checked 2026-10-19
    "fortigate": (2846, "1.6.10", "Splunk_TA_fortinet_fortigate"),
    "paloalto": (7523, "4.0.0", "Splunk_TA_paloalto_networks"),
}
UA = {"User-Agent": "LabConsole-splunkbase-fetch/1.0"}


def login() -> str:
    c = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("splunkbase/account")
    body = urllib.parse.urlencode({"username": c.username, "password": c.password}).encode()
    req = urllib.request.Request("https://splunkbase.splunk.com/api/account:login/", data=body, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", e.read().decode("utf-8", "replace")))[:400]
        raise SystemExit(f"Splunkbase login failed: HTTP {e.code} server={e.headers.get('Server')} "
                         f"body: {detail}")
    m = re.search(r"<id>([^<]+)</id>", text)
    if not m:
        raise SystemExit("Splunkbase login: no token in the response")
    return m.group(1).strip()


def download(token: str, app_id: int, version: str) -> bytes:
    url = f"https://splunkbase.splunk.com/app/{app_id}/release/{version}/download/?origin=sb&lang=en-US"
    req = urllib.request.Request(url, headers={**UA, "X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=600) as r:  # follows the redirect to the file host
        return r.read()


def inspect(data: bytes, want_folder: str) -> dict:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        names = tf.getnames()
        bad = [n for n in names if n.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", n)
               or ".." in Path(n).parts]
        if bad:
            raise ValueError(f"unsafe member paths: {bad[:3]}")
        tops = {Path(n).parts[0] for n in names if n not in (".", "./")}
        if tops != {want_folder}:
            raise ValueError(f"top-level folders {sorted(tops)} != {want_folder}")
        conf = tf.extractfile(f"{want_folder}/default/app.conf")
        text = conf.read().decode("utf-8", "replace") if conf else ""
    def val(key: str) -> str:
        m = re.search(rf"(?m)^\s*{key}\s*=\s*(.+?)\s*$", text)
        return m.group(1) if m else ""
    has_inputs = any(n.endswith(("default/inputs.conf",)) for n in names)
    bins = sorted({Path(n).suffix.lower() for n in names if "/bin/" in n and Path(n).suffix})
    return {"files": len(names), "version": val("version"), "id": val("id"), "label": val("label"),
            "has_default_inputs": has_inputs, "bin_types": bins}


def main() -> None:
    keys = sys.argv[2:] or list(RELEASES)
    OUT.mkdir(exist_ok=True)
    token = login()
    print("== logged in to Splunkbase")
    for k in keys:
        app_id, ver, folder = RELEASES[k]
        try:
            data = download(token, app_id, ver)
        except urllib.error.HTTPError as e:
            print(f"   {k}: download failed HTTP {e.code} ({app_id} {ver})")
            continue
        try:
            info = inspect(data, folder)
        except (tarfile.TarError, ValueError) as e:
            print(f"   {k}: REJECTED - {e} (not saved)")
            continue
        if info["version"] != ver:
            print(f"   {k}: REJECTED - app.conf version {info['version']!r} != {ver} (not saved)")
            continue
        path = OUT / f"{folder}-{ver}.tgz"
        path.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        print(f"   {k}: {path.name}  {len(data):,} bytes  sha256 {sha[:16]}...  {json.dumps(info)}")


main()
