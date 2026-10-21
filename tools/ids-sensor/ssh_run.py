"""Run commands on the IDS VM over the console's SSH transport (host key pinned in the inventory).

  hostkey <target>                          pre-auth: print the server's host key fingerprint (no credentials sent)
  run <target> <cmd> [timeout]              run one command, print output
  put <target> <local> <remote>             SFTP upload (binary, byte-exact)
  stage <target> <stage> [args...]          upload provision.sh to ~/ and `sudo bash provision.sh <stage> ...`

usage: python -I -X utf8 tools/ids-sensor/ssh_run.py <backend> <action> <target> ...
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BACKEND))
from app.config import Settings  # noqa: E402
from app.core.audit import AuditLog  # noqa: E402
from app.core.credentials import CredentialStore  # noqa: E402
from app.core.pool import SessionPool  # noqa: E402
from app.models.inventory import Inventory  # noqa: E402

ACTION, TARGET, ARGS = sys.argv[2], sys.argv[3], sys.argv[4:]
HERE = Path(__file__).resolve().parent


async def main() -> None:
    s = Settings.load()
    inv = Inventory.load(s.inventory_path)
    target = next(t for t in inv.all() if t.name == TARGET)
    if ACTION == "hostkey":
        import asyncssh
        for alg in ("ssh-ed25519", "ecdsa-sha2-nistp256", "rsa-sha2-512"):
            key = await asyncssh.get_server_host_key(target.address, 22, server_host_key_algs=[alg])
            print(alg, key.get_fingerprint() if key else "none")
        return
    if not target.ssh_fingerprint:
        raise SystemExit(f"{TARGET} has no ssh_fingerprint pinned; read it with `hostkey` and pin it first")
    pool = SessionPool(settings=s, inventory=inv, creds=CredentialStore.load(BACKEND.parent / "config" / "credentials.example.yaml"))
    audit = AuditLog(s.audit_abs)
    tr = await pool.shell(TARGET)
    if ACTION == "put":
        n = await tr.put_file(ARGS[0], ARGS[1])
        print(f"put {n} bytes -> {ARGS[1]}")
        audit.record(action="ids.ssh-put", target=TARGET, transport=str(tr.name), result="ok", detail={"remote": ARGS[1], "bytes": n})
        return
    if ACTION == "stage":
        await tr.put_file(str(HERE / "provision.sh"), "provision.sh")
        cmd, timeout = "sudo bash ~/provision.sh " + " ".join(ARGS) + " 2>&1", 3600
    elif ACTION == "run":
        cmd, timeout = ARGS[0], int(ARGS[1]) if len(ARGS) > 1 else 300
    else:
        raise SystemExit(f"unknown action {ACTION}")
    res = await tr.run(cmd, timeout=timeout)
    print(res.stdout.rstrip())
    if res.stderr.strip():
        print("[stderr]", res.stderr.strip()[-3000:])
    ok = res.exit_code in (0, None)
    print(f"[exit {res.exit_code}]")
    audit.record(action=f"ids.ssh-{ACTION}", target=TARGET, transport=str(tr.name), result="ok" if ok else "error",
                 detail={"cmd": cmd[:200]})
    await pool.close_all()
    sys.exit(0 if ok else 1)


asyncio.run(main())
