"""Build the cloud-init NoCloud seed ISO (volume label CIDATA) for the L4H1_IDS Ubuntu autoinstall.

Reads the idsadmin password from the credentials file (hashed with SHA-512 crypt, never written in
clear) and the public key next to ssh_key_file. Needs pycdlib + passlib (scratch venv, not the backend).

usage: python -I make_seed.py <credentials.yaml> <out.iso>
"""
import io
import sys
from pathlib import Path

import pycdlib
import yaml
from passlib.hash import sha512_crypt

CRED = "L4H1_IDS/idsadmin"
HOSTNAME = "l4h1-ids"
MAC_MGMT, MAC_CAP = "00:15:5d:a9:81:e0", "00:15:5d:a9:81:e1"   # static MACs set on the VM adapters
IP, GW, DNS = "10.5.20.60/24", "10.5.20.254", "10.1.20.17"

entry = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["credentials"][CRED]
pubkey = Path(entry["ssh_key_file"] + ".pub").read_text().strip()
pwhash = sha512_crypt.using(rounds=656000).hash(entry["password"])

user_data = f"""#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard: {{layout: us}}
  timezone: Asia/Singapore
  refresh-installer: {{update: false}}
  source: {{id: ubuntu-server}}
  apt:
    geoip: false
    fallback: offline-install
  network:
    version: 2
    ethernets:
      mgmt0:
        match: {{macaddress: "{MAC_MGMT}"}}
        set-name: mgmt0
        addresses: [{IP}]
        routes: [{{to: default, via: {GW}}}]
        nameservers: {{addresses: [{DNS}], search: [np.local]}}
      cap0:
        match: {{macaddress: "{MAC_CAP}"}}
        set-name: cap0
        dhcp4: false
        dhcp6: false
        link-local: []
        accept-ra: false
        optional: true
  storage:
    layout:
      name: lvm
      sizing-policy: all
      match: {{size: smallest}}
  identity:
    hostname: {HOSTNAME}
    username: {entry["username"]}
    realname: IDS admin
    password: "{pwhash}"
  ssh:
    install-server: true
    allow-pw: true
    authorized-keys:
      - "{pubkey}"
  late-commands:
    - "echo '{entry["username"]} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/90-{entry["username"]}"
    - "chmod 0440 /target/etc/sudoers.d/90-{entry["username"]}"
  shutdown: poweroff
"""
meta_data = f"instance-id: {HOSTNAME}-20261020\nlocal-hostname: {HOSTNAME}\n"

iso = pycdlib.PyCdlib()
iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident="CIDATA")
for name, body in (("user-data", user_data), ("meta-data", meta_data)):
    data = body.encode("utf-8")
    iso.add_fp(io.BytesIO(data), len(data), f"/{name.upper().replace('-', '')}.;1",
               rr_name=name, joliet_path=f"/{name}")
iso.write(sys.argv[2])
iso.close()
print(f"wrote {sys.argv[2]} (user {entry['username']}, key {pubkey.split()[-1]})")
