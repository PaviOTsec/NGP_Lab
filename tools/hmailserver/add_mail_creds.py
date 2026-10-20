"""Add the hMailServer credentials to the credentials file (once; never overwrites).

usage: python -I tools/hmailserver/add_mail_creds.py <credentials.yaml>

hmailserver/Administrator: random 24 chars (hMailServer Administrator / COM API).
mail/<account>: training-pattern mailbox passwords (<Name>@Mail26), easy to read out to students.
"""
import re
import secrets
import string
import sys
from pathlib import Path

DOMAIN = "mail.np.local"
ACCOUNTS = ["admin"] + [f"student{i}" for i in range(1, 9)] + ["trainee", "remoteIT"]

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8-sig")
if "hmailserver/Administrator:" in text:
    sys.exit("hmailserver/Administrator already present; not changed")
alphabet = string.ascii_letters + string.digits
lines = [
    "  # =========================================================================================",
    f"  # MAIL - hMailServer 5.7.1 on L4H1_MailServer (10.4.20.21), domain {DOMAIN} (2026-10-20).",
    "  # hmailserver/Administrator = hMailServer Administrator GUI / COM API (random).",
    "  # mail/* = mailboxes; IMAP 143 / POP3 110 / SMTP 587 (auth) at mail.np.local.",
    "  # =========================================================================================",
    "  hmailserver/Administrator:",
    "    username: Administrator",
    f"    password: \"{''.join(secrets.choice(alphabet) for _ in range(24))}\"",
]
for a in ACCOUNTS:
    lines += [f"  mail/{a}:", f"    username: {a}@{DOMAIN}", f"    password: \"{a[0].upper() + a[1:]}@Mail26\""]
block = "\n".join(lines) + "\n"
m = re.search(r"(?m)^  # --- inline key example ---\n", text)
if not m:
    sys.exit("anchor '# --- inline key example ---' not found")
p.write_text(text[:m.start()] + block + "\n" + text[m.start():], encoding="utf-8")
print(f"inserted {len(ACCOUNTS) + 1} entries before line", text[:m.start()].count("\n") + 1)
