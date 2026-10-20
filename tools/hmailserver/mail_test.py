"""End-to-end mail test against hMailServer (10.4.20.21) from MC01.

usage: python -I -X utf8 tools/hmailserver/mail_test.py <backend-dir>

1. student1 -> remoteIT over SMTP 587 with AUTH, 2. remoteIT reads it over IMAP 143,
3. POP3 110 login, 4. negative: unauthenticated relay to an outside domain is refused,
5. negative: unauthenticated MAIL FROM a local address (spoof) is refused.
"""
import imaplib
import poplib
import smtplib
import sys
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

HOST = "10.4.20.21"
creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
s1, rit = creds.credential("mail/student1"), creds.credential("mail/remoteIT")
tag = uuid.uuid4().hex[:8]
results = {}

msg = EmailMessage()
msg["From"], msg["To"], msg["Subject"] = s1.username, rit.username, f"lab mail test {tag}"
msg.set_content("Test message from MC01 (tools/hmailserver/mail_test.py).")
with smtplib.SMTP(HOST, 587, timeout=15) as smtp:
    smtp.ehlo("mc01")
    smtp.login(s1.username, s1.password)
    smtp.send_message(msg)
results["smtp 587 auth send"] = "ok"

time.sleep(3)
imap = imaplib.IMAP4(HOST, 143, timeout=15)
imap.login(rit.username, rit.password)
imap.select("INBOX", readonly=True)
typ, data = imap.search(None, "SUBJECT", f'"lab mail test {tag}"')
results["imap 143 login + message arrived"] = "ok" if data and data[0].split() else "NOT FOUND"
imap.logout()

pop = poplib.POP3(HOST, 110, timeout=15)
pop.user(s1.username)
pop.pass_(s1.password)
results["pop3 110 login"] = f"ok ({pop.stat()[0]} msgs)"
pop.quit()


def refused(mail_from: str, rcpt: str) -> str:
    with smtplib.SMTP(HOST, 25, timeout=15) as smtp:
        smtp.ehlo("mc01")
        code, _ = smtp.mail(mail_from)
        if code >= 400:
            return f"refused at MAIL FROM ({code})"
        code, _ = smtp.rcpt(rcpt)
        return f"refused at RCPT ({code})" if code >= 400 else f"ACCEPTED ({code})"


results["no relay: outside -> outside"] = refused("someone@example.com", "victim@example.org")
results["no spoof: unauth local sender"] = refused(s1.username, rit.username)
for k, v in results.items():
    print(f"   {k:34} {v}")
