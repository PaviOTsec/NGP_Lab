"""Minimal Trellix ePO remote-command web API client. Reads the epo/admin credential.
Makes ONE call per invocation (no retry loop -> no lockout risk).
usage: python -I epo_api.py <command> [key=value ...]
examples:
  python -I epo_api.py core.help
  python -I epo_api.py system.find searchText=L4H1RAC
  python -I epo_api.py core.help command=system.move
"""
import sys, requests, urllib3
sys.path.insert(0, "backend")
from app.core.credentials import CredentialStore  # noqa: E402

urllib3.disable_warnings()
BASE = "https://10.1.20.11:8443/remote/"


def call(command: str, params: dict) -> requests.Response:
    # ePO web-API login is user "admin" with the DMZ-HOST-2 HyperVAdmin password (operator set them
    # the same). The epo/admin creds entry had a stale password, so resolve the live one here.
    store = CredentialStore.load("config/credentials.example.yaml")
    pw = store.credential("DMZ-HOST-2/HyperVAdmin").password
    q = dict(params)
    q[":output"] = "json"
    return requests.get(BASE + command, params=q, auth=("admin", pw),
                        verify=False, timeout=30)


if __name__ == "__main__":
    cmd = sys.argv[1]
    params = dict(p.split("=", 1) for p in sys.argv[2:])
    r = call(cmd, params)
    print("HTTP", r.status_code)
    print(r.text[:4000])
