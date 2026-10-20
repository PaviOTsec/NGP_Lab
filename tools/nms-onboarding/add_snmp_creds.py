import re, secrets, string, sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8-sig")
if "snmpv3/nms:" in text:
    sys.exit("snmpv3/nms already present; not changed")
alphabet = string.ascii_letters + string.digits
gen = lambda: "".join(secrets.choice(alphabet) for _ in range(24))
block = (
    "  # SNMPv3 user for SINEC NMS (generated 2026-10-12, 24 chars alphanumeric).\n"
    "  # Same user on every NMS-monitored device: SHA-256 + AES-128; OT-FW uses SHA-1 + AES-128.\n"
    f"  snmpv3/nms:                            # authentication password\n"
    f"    username: sinecnms\n"
    f"    password: \"{gen()}\"\n"
    f"  snmpv3/nms-priv:                       # privacy (encryption) password\n"
    f"    username: sinecnms\n"
    f"    password: \"{gen()}\"\n"
)
m = re.search(r"(?m)^  network/admin:\n(?:    .*\n)+", text)
if not m:
    sys.exit("network/admin entry not found")
p.write_text(text[:m.end()] + block + text[m.end():], encoding="utf-8")
print("inserted after line", text[:m.end()].count("\n"))
