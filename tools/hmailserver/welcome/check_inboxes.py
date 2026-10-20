"""Check every lab mailbox (except admin) over IMAP for the welcome email and its parts.

usage: python -I -X utf8 tools/hmailserver/welcome/check_inboxes.py <backend-dir>
"""
import email
import imaplib
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
for name in creds.names():
    if not name.startswith("mail/") or name == "mail/admin":
        continue
    c = creds.credential(name)
    m = imaplib.IMAP4("10.4.20.21", 143, timeout=15)
    m.login(c.username, c.password)
    m.select("INBOX", readonly=True)
    _, data = m.search(None, "SUBJECT", '"Cyber Excellence Lab"')
    ids = data[0].split()
    state = "MISSING"
    if ids:
        _, raw = m.fetch(ids[-1], "(BODY.PEEK[])")
        types = {p.get_content_type() for p in email.message_from_bytes(raw[0][1]).walk()}
        state = ("delivered: html + text, logo inline" if {"text/html", "text/plain", "image/png"} <= types
                 else f"delivered, parts={sorted(types)}")
    print(f"   {c.username:28} {state}")
    m.logout()
