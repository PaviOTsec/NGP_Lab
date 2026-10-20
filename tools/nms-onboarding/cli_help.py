"""Read CLI context help ('?') for a config-mode command WITHOUT executing anything.

Each query is its own SSH session: enter config mode, type the partial command ending in
'?' (no Enter), read the help, then disconnect — the partial line is discarded with the
session, so nothing is ever executed or saved. Host key pinned on the auth connection.

usage: python -I nms_cli_help.py <backend_dir> <ip> <ssh_fp> <config-enter-cmd> <query>...
"""
import asyncio
import re
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
IP, FP, ENTER = sys.argv[2], sys.argv[3], sys.argv[4]
QUERIES = sys.argv[5:] or [""]  # PowerShell 5.1 drops empty "" args: no query = show-only run
sys.path.insert(0, str(BACKEND))
import asyncssh  # noqa: E402

from app.core.credentials import CredentialStore  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


async def drain(proc, idle=4.0, maxwait=30.0) -> str:
    buf, loop = "", asyncio.get_running_loop()
    end = loop.time() + maxwait
    while loop.time() < end:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(65536), timeout=idle)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        buf += chunk
    return ANSI.sub("", buf).replace("\r", "")


async def one(cred, query: str) -> None:
    key = await asyncssh.get_server_host_key(IP, 22)
    if key.get_fingerprint() != FP:
        sys.exit("host key mismatch; no credentials sent")
    conn = await asyncssh.connect(IP, username=cred.username, password=cred.password,
                                  known_hosts=([key], [], []), client_keys=None, agent_path=None)
    try:
        proc = await conn.create_process(term_type="vt100", term_size=(220, 60))
        await drain(proc)
        prompt = ""
        for step in ENTER.split(";;"):  # mode-entry or show commands (e.g. configure terminal;;ntp)
            proc.stdin.write(step + "\n")
            prompt += await drain(proc)
        print(f"--- [{IP}] after '{ENTER}':\n{prompt.strip()[-6000:]}")
        if query:
            proc.stdin.write(query)  # NO newline
            print(f"--- [{IP}] help for: {query!r}\n{await drain(proc)}")
    finally:
        conn.close()  # partial line dies with the session


async def main() -> None:
    cred = CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml").credential("network/admin")
    for q in QUERIES:
        await one(cred, q)


asyncio.run(main())
