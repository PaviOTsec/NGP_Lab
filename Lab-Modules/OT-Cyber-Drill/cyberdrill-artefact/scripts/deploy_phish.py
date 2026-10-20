"""Deploy the GP-0 phishing artefacts to Kali (SFTP, host key pinned) and lay out the drill dir.
usage: python -I deploy_phish.py"""
import asyncio, sys, hashlib, base64
from pathlib import Path
sys.path.insert(0, "backend")
import asyncssh  # noqa: E402

KALI, PIN = "10.5.20.50", "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"
ART = Path("Lab-Modules/OT-Cyber-Drill/cyberdrill-artefact/gp0-phish")
# local -> remote
FILES = {
    ART / "Mailbox_Security_Update.hta": "/home/kali/drill/web/Mailbox_Security_Update.hta",
    ART / "revshell.ps1": "/home/kali/drill/web/s.ps1",
    ART / "phish_email.py": "/home/kali/drill/phish_email.py",
    ART / "thankyou_email.py": "/home/kali/drill/thankyou_email.py",
}


async def main() -> None:
    async with asyncssh.connect(KALI, username="kali", password="kali", known_hosts=None) as c:
        k = c.get_server_host_key()
        assert "SHA256:" + base64.b64encode(hashlib.sha256(k.public_data).digest()).decode().rstrip("=") == PIN
        await c.run("mkdir -p /home/kali/drill/web /home/kali/drill/loot")
        async with c.start_sftp_client() as sftp:
            for local, remote in FILES.items():
                await sftp.put(str(local), remote)
        r = await c.run("ls -la /home/kali/drill /home/kali/drill/web", check=False)
        print(r.stdout)


asyncio.run(main())
