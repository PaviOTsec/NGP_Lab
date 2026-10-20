"""Send the lab welcome email from admin@mail.np.local to every other lab mailbox.

usage: python -I -X utf8 tools/hmailserver/welcome/send_welcome.py <backend-dir> [--preview <out.html>] [--only <address>]

One personalised message per recipient (HTML + plain text, logo embedded inline as cid: so the
lab VMs need no internet). Sent over SMTP 587 with AUTH as admin. No passwords in the message.
--preview writes the HTML for the first recipient (logo as a file link) and sends nothing.
"""
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.core.credentials import CredentialStore  # noqa: E402

HERE = Path(__file__).resolve().parent
HOST = "10.4.20.21"
SUBJECT = "Welcome to the Ngee Ann Polytechnic OT & Cyber Excellence Lab"


def display_name(address: str) -> str:
    local = address.split("@")[0]
    if local.startswith("student") and local[7:].isdigit():
        return f"Student {local[7:]}"
    return {"remoteIT": "Remote IT", "trainee": "Trainee"}.get(local, local)


def plain(name: str, address: str) -> str:
    return f"""Dear {name},

Welcome to the Operational Technology & Cyber Excellence Lab at Ngee Ann Polytechnic.
Your lab mailbox is ready. You'll use it for exercises, announcements from your
instructors, and the cyber drills that run on the lab network.

YOUR LAB MAILBOX
  Email address    {address}
  Incoming (IMAP)  mail.np.local, port 143
  Outgoing (SMTP)  mail.np.local, port 587, sign-in required
  Password         Given to you by your instructor. It is never sent by email.

WHAT YOU'LL WORK WITH
  - A segmented industrial network, modelled on the Purdue levels, with real
    industrial switches and firewalls
  - A security operations stack: SIEM, network monitoring and centralised logging
  - Hands-on Red Team / Blue Team cyber drills in a safe, isolated environment

LAB GROUND RULES
  1. Work only on the systems your instructor assigns to you.
  2. Plant-floor equipment (controllers and field devices) is off-limits unless
     your instructor says otherwise.
  3. Never share passwords by email or chat. No genuine lab message will ever ask for yours.
  4. Report anything unusual, including suspicious emails, to admin@mail.np.local.

We're glad to have you on board. See you in the lab!

Warm regards,
Lab Administrator
Operational Technology & Cyber Excellence Lab
Ngee Ann Polytechnic
admin@mail.np.local

--
This mailbox belongs to an isolated training network. Lab mail may be logged and
monitored for training and security exercises.
"""


def main() -> None:
    args = sys.argv[2:]
    creds = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml")
    admin = creds.credential("mail/admin")
    recipients = [creds.credential(n).username for n in creds.names()
                  if n.startswith("mail/") and n != "mail/admin"]
    if "--only" in args:
        recipients = [args[args.index("--only") + 1]]
    template = (HERE / "welcome.html").read_text(encoding="utf-8")
    logo = (HERE / "np-logo.png").read_bytes()

    if "--preview" in args:
        out = Path(args[args.index("--preview") + 1])
        html = template.replace("cid:{logo_cid}", (HERE / "np-logo.png").as_uri())
        out.write_text(html.replace("{display_name}", display_name(recipients[0]))
                       .replace("{address}", recipients[0]), encoding="utf-8")
        print(f"preview written: {out}")
        return

    with smtplib.SMTP(HOST, 587, timeout=20) as smtp:
        smtp.ehlo("mc01")
        smtp.login(admin.username, admin.password)
        for rcpt in recipients:
            name = display_name(rcpt)
            cid = make_msgid(domain="mail.np.local")
            msg = EmailMessage()
            msg["From"] = formataddr(("OT & Cyber Excellence Lab", admin.username))
            msg["To"] = formataddr((name, rcpt))
            msg["Subject"] = SUBJECT
            msg.set_content(plain(name, rcpt))
            html = (template.replace("{logo_cid}", cid[1:-1]).replace("{display_name}", name)
                    .replace("{address}", rcpt))
            msg.add_alternative(html, subtype="html")
            msg.get_payload()[1].add_related(logo, maintype="image", subtype="png", cid=cid,
                                             filename="np-logo.png")
            smtp.send_message(msg)
            print(f"   sent -> {rcpt}")
    print(f"== {len(recipients)} welcome emails sent from {admin.username}")


main()
