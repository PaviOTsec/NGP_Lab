#!/usr/bin/env bash
# L4H1_IDS provisioning (Ubuntu 24.04). Run as root, one stage at a time:
#   sudo bash provision.sh <base|suricata|zeek|uf|status>
# Package downloads go through MC01's temporary proxy (tools/ids-sensor/mini_proxy.py); nothing here
# needs internet once installed. Capture NIC = cap0 (no IP, promiscuous); data = /data (second disk).
set -euo pipefail
PROXY="http://10.1.20.56:3128"
CAP=cap0
HOME_NETS="[10.0.0.0/8,172.16.0.0/12,192.168.0.0/16]"
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a

with_proxy() { http_proxy=$PROXY https_proxy=$PROXY HTTP_PROXY=$PROXY HTTPS_PROXY=$PROXY "$@"; }

stage_base() {
  cat > /etc/apt/apt.conf.d/95labproxy <<EOF
Acquire::http::Proxy "$PROXY";
Acquire::https::Proxy "$PROXY";
Acquire::http::Pipeline-Depth "0";
EOF
  # data disk: the disk with no partitions that isn't the OS disk
  if ! findmnt -n /data >/dev/null; then
    DISK=$(lsblk -dnpo NAME,TYPE | awk '$2=="disk"{print $1}' | while read -r d; do
             [ -z "$(lsblk -nrpo NAME "$d" | sed 1d)" ] && echo "$d"; done | head -n1)
    [ -n "$DISK" ] || { echo "no empty data disk found" >&2; exit 1; }
    echo "formatting $DISK as /data"
    parted -s "$DISK" mklabel gpt mkpart data ext4 0% 100%
    udevadm settle
    mkfs.ext4 -q -L IDSDATA "${DISK}1"
    mkdir -p /data
    echo "LABEL=IDSDATA /data ext4 defaults,noatime 0 2" >> /etc/fstab
    systemctl daemon-reload
    mount /data
  fi
  apt-get update -q
  apt-get -yq full-upgrade
  apt-get -yq install linux-tools-virtual linux-cloud-tools-virtual ethtool jq tcpdump git curl gnupg \
    software-properties-common python3-yaml cmake make g++ libpcap-dev libssl-dev swig zlib1g-dev
  # time from SINEC INS, like the switches/firewalls
  mkdir -p /etc/systemd/timesyncd.conf.d
  printf '[Time]\nNTP=10.1.20.21\n' > /etc/systemd/timesyncd.conf.d/lab.conf
  systemctl restart systemd-timesyncd
  # capture NIC: up, promiscuous, offloads off (so Zeek/Suricata see real packets), no IP
  cat > /etc/systemd/system/capture-nic.service <<EOF
[Unit]
Description=Prepare $CAP for passive capture (promisc, offloads off)
After=network.target
Before=suricata.service zeek.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/ip link set $CAP up promisc on
ExecStart=-/usr/sbin/ethtool -K $CAP rx off tx off sg off tso off gso off gro off lro off

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now capture-nic.service
  echo "base OK"
}

stage_suricata() {
  with_proxy add-apt-repository -y ppa:oisf/suricata-stable
  apt-get update -q
  apt-get -yq install suricata
  systemctl stop suricata || true
  mkdir -p /data/suricata
  CORES=4
  # NB: an include replaces whole top-level sections, so only self-contained ones go here (never
  # vars/app-layer: replacing vars drops the port groups the ET rules need). The stock HOME_NET is
  # already all of RFC1918 ($HOME_NETS); ICS parsers are switched on in suricata.yaml itself below.
  cat > /etc/suricata/lab-override.yaml <<EOF
%YAML 1.1
---
default-log-dir: /data/suricata
af-packet:
  - interface: $CAP
    threads: $CORES
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes
    use-mmap: yes
    tpacket-v3: yes
    ring-size: 200000
    checksum-checks: no
outputs:
  - fast:
      enabled: no
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      community-id: yes
      community-id-seed: 0
      types:
        - alert:
            tagged-packets: yes
        - anomaly:
            enabled: yes
        - stats:
            totals: yes
            threads: no
            deltas: no
  - stats:
      enabled: yes
      filename: stats.log
      totals: yes
      threads: no
stats:
  enabled: yes
  interval: 60
EOF
  stage_runsock
  grep -q '^include: /etc/suricata/lab-override.yaml' /etc/suricata/suricata.yaml ||
    printf '\ninclude: /etc/suricata/lab-override.yaml\n' >> /etc/suricata/suricata.yaml
  # ICS app-layer parsers: modbus + dnp3 ship disabled; enip is on by default
  for proto in modbus dnp3 enip; do
    sed -i "/^    $proto:/,/^      enabled:/ s/^      enabled: no/      enabled: yes/" /etc/suricata/suricata.yaml
  done
  suricata --dump-config -c /etc/suricata/suricata.yaml | grep -E '^(vars\.address-groups\.HOME_NET|app-layer\.protocols\.(modbus|dnp3|enip)\.enabled|af-packet\.0\.interface|default-log-dir) '
  # (the PPA unit runs `suricata --af-packet ... --user suricata`; the interface comes from af-packet above)
  with_proxy suricata-update update-sources
  with_proxy suricata-update enable-source et/open
  with_proxy suricata-update --no-test
  suricata -T -c /etc/suricata/suricata.yaml -v | tail -n 5
  # the service drops to user suricata: it must own its log dir (the -T run above, as root, creates
  # root-owned eve.json/stats.log, which then fail with Permission denied and nothing is logged)
  chown -R suricata:suricata /data/suricata
  cat > /etc/logrotate.d/suricata-lab <<'EOF'
/data/suricata/*.log /data/suricata/*.json {
    su suricata suricata
    daily
    rotate 14
    missingok
    compress
    delaycompress
    sharedscripts
    postrotate
        /bin/kill -HUP $(cat /var/run/suricata.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF
  systemctl enable suricata
  systemctl restart suricata
  sleep 5
  systemctl is-active suricata
  echo "suricata OK: $(suricata -V)"
}

stage_runsock() {
  # Suricata drops to user suricata before creating its unix-socket dir; /run is tmpfs, so after a
  # reboot /run/suricata is gone and suricatasc stops working. Recreate it at every boot, owned by suricata.
  echo 'd /run/suricata 0750 suricata suricata -' > /etc/tmpfiles.d/suricata-lab.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/suricata-lab.conf
  if systemctl is-active -q suricata; then
    systemctl restart suricata
    for _ in $(seq 1 60); do [ -S /run/suricata/suricata-command.socket ] && break; sleep 2; done
    ls -l /run/suricata/
    suricatasc -c uptime /run/suricata/suricata-command.socket
  fi
  echo "runsock OK"
}

stage_extnet() {
  # Operator 2026-10-21: treat the WAN (10.5.20.0/24: Kali, RAC, trainee side) and OT L2 (192.168.20.0/24)
  # as untrusted, so `$EXTERNAL_NET -> $HOME_NET` rules fire for attacks launched from there.
  # HOME_NET stays all of RFC1918 (overlap is fine), so attacks *within* those subnets still match.
  # Suricata's address groups can't re-add a range inside a negation (`[!$HOME_NET,10.5.20.0/24]`
  # would cut it out again), so "public internet" is written out as the complement of RFC1918.
  local Y=/etc/suricata/suricata.yaml
  local PUBLIC='[0.0.0.0/5,8.0.0.0/7,11.0.0.0/8,12.0.0.0/6,16.0.0.0/4,32.0.0.0/3,64.0.0.0/2,128.0.0.0/3,160.0.0.0/5,168.0.0.0/6,172.0.0.0/12,172.32.0.0/11,172.64.0.0/10,172.128.0.0/9,173.0.0.0/8,174.0.0.0/7,176.0.0.0/4,192.0.0.0/9,192.128.0.0/11,192.160.0.0/13,192.169.0.0/16,192.170.0.0/15,192.172.0.0/14,192.176.0.0/12,192.192.0.0/10,193.0.0.0/8,194.0.0.0/7,196.0.0.0/6,200.0.0.0/5,208.0.0.0/4,224.0.0.0/3]'
  local UNTRUSTED='[10.5.20.0/24,192.168.20.0/24]'
  [ "$(grep -cE '^    EXTERNAL_NET:' $Y)" = 1 ] || { echo "expected exactly one EXTERNAL_NET line in $Y" >&2; exit 1; }
  local BAK=$Y.bak-$(date +%Y%m%d-%H%M%S)
  cp -p $Y "$BAK"
  sed -i -E '/^    (PUBLIC_NET|LAB_UNTRUSTED_NET):/d' $Y
  sed -i -E "s|^    EXTERNAL_NET: .*|    EXTERNAL_NET: \"[\$PUBLIC_NET,\$LAB_UNTRUSTED_NET]\"\n    PUBLIC_NET: \"$PUBLIC\"\n    LAB_UNTRUSTED_NET: \"$UNTRUSTED\"|" $Y
  if ! suricata -T -v -c $Y >/tmp/suricata-T.log 2>&1; then
    cp -p "$BAK" $Y; tail -n 15 /tmp/suricata-T.log; echo "config test FAILED - restored $BAK" >&2; exit 1
  fi
  grep -E 'rules successfully loaded|signatures processed' /tmp/suricata-T.log | tail -n 2 || true
  suricata --dump-config -c $Y | grep -E '^vars\.address-groups\.(HOME_NET|EXTERNAL_NET|LAB_UNTRUSTED_NET) ' || true
  systemctl restart suricata
  for _ in $(seq 1 60); do grep -q 'Engine started' /data/suricata/suricata.log 2>/dev/null && [ /data/suricata/suricata.log -nt "$BAK" ] && break; sleep 2; done
  systemctl is-active suricata
  tail -n 1 /data/suricata/suricata.log
  echo "extnet OK (backup $BAK)"
}

stage_zeek() {
  . /etc/os-release
  echo "deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_${VERSION_ID}/ /" > /etc/apt/sources.list.d/security-zeek.list
  with_proxy curl -fsSL "https://download.opensuse.org/repositories/security:zeek/xUbuntu_${VERSION_ID}/Release.key" |
    gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/security_zeek.gpg
  apt-get update -q
  # newest LTS line available (zeek-8.0 / zeek-7.0), fall back to the feature release
  PKG=$(apt-cache pkgnames | grep -E '^zeek-[0-9]+\.[0-9]+$' | sort -V | tail -n1)
  apt-get -yq install "${PKG:-zeek}"
  ZEEK=/opt/zeek
  export PATH=$ZEEK/bin:$PATH
  echo "export PATH=$ZEEK/bin:\$PATH" > /etc/profile.d/zeek.sh
  mkdir -p /data/zeek/logs /data/zeek/spool
  cat > $ZEEK/etc/node.cfg <<EOF
[logger-1]
type=logger
host=localhost

[manager]
type=manager
host=localhost

[proxy-1]
type=proxy
host=localhost

[worker-1]
type=worker
host=localhost
interface=af_packet::$CAP
lb_method=custom
lb_procs=4
af_packet_fanout_id=23
af_packet_fanout_mode=AF_Packet::FANOUT_HASH
EOF
  cat > $ZEEK/etc/networks.cfg <<'EOF'
10.0.0.0/8       RFC1918 (lab: DMZ 10.1.20/24, L4 10.4.20/24, WAN 10.5.20/24)
172.16.0.0/12    RFC1918
192.168.0.0/16   RFC1918 (mgmt 192.168.100/24, OT 192.168.1-4,20,30/24)
EOF
  sed -i -e 's|^LogDir *=.*|LogDir = /data/zeek/logs|' -e 's|^SpoolDir *=.*|SpoolDir = /data/zeek/spool|' \
         -e 's|^LogExpireInterval *=.*|LogExpireInterval = 30day|' $ZEEK/etc/zeekctl.cfg
  grep -q '^SpoolDir' $ZEEK/etc/zeekctl.cfg || echo 'SpoolDir = /data/zeek/spool' >> $ZEEK/etc/zeekctl.cfg
  grep -q '^LogExpireInterval' $ZEEK/etc/zeekctl.cfg || echo 'LogExpireInterval = 30day' >> $ZEEK/etc/zeekctl.cfg
  # zeekctl's websocket client needs python websockets>=11 (not in noble); plain broker is enough
  grep -q '^UseWebSocket' $ZEEK/etc/zeekctl.cfg && sed -i 's/^UseWebSocket *=.*/UseWebSocket = 0/' $ZEEK/etc/zeekctl.cfg ||
    echo 'UseWebSocket = 0' >> $ZEEK/etc/zeekctl.cfg
  # ICS protocol parsers (CISA/INL ICSNPP), built against this Zeek
  with_proxy git config --global http.proxy "$PROXY"
  zkg autoconfig --force >/dev/null
  # (icsnpp-profinet-io-cm left out: on Zeek 8.0 its .hlto fails to load - undefined
  #  c_functions::bytesToUuid - and that breaks every node's script check; seen on Zeek 9.0.0, 2026-10-20)
  for p in icsnpp-modbus icsnpp-dnp3 icsnpp-enip icsnpp-s7comm icsnpp-opcua-binary icsnpp-bacnet; do
    with_proxy zkg install --force --skiptests "$p" || echo "WARN: $p failed"
  done
  grep -q 'lab additions' $ZEEK/share/zeek/site/local.zeek || cat >> $ZEEK/share/zeek/site/local.zeek <<'EOF'

# ---- lab additions (tools/ids-sensor/provision.sh)
@load policy/tuning/json-logs.zeek
@load policy/protocols/conn/community-id-logging
@load policy/protocols/conn/known-hosts
@load policy/protocols/conn/known-services
@load policy/protocols/modbus/known-masters-slaves
@load policy/protocols/modbus/track-memmap
@load packages
redef ignore_checksums = T;
EOF
  cat > /etc/systemd/system/zeek.service <<EOF
[Unit]
Description=Zeek network security monitor (zeekctl cluster)
After=network-online.target capture-nic.service
Wants=network-online.target

[Service]
Type=forking
ExecStartPre=$ZEEK/bin/zeekctl install
ExecStart=$ZEEK/bin/zeekctl start
ExecStop=$ZEEK/bin/zeekctl stop
TimeoutStartSec=300
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  echo "*/5 * * * * root $ZEEK/bin/zeekctl cron" > /etc/cron.d/zeekctl
  $ZEEK/bin/zeekctl check
  systemctl daemon-reload
  systemctl enable zeek
  systemctl restart zeek
  sleep 10
  $ZEEK/bin/zeekctl status
  echo "zeek OK: $($ZEEK/bin/zeek --version)"
}

stage_uf() {
  # $1 = path of the .deb (pushed by SFTP); deployment server pushes outputs + inputs
  DEB=${1:?deb path}
  id splunkfwd >/dev/null 2>&1 || true
  dpkg -i "$DEB"
  UF=/opt/splunkforwarder
  if [ ! -f $UF/etc/passwd ]; then
    PW=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)
    printf '[user_info]\nUSERNAME = admin\nPASSWORD = %s\n' "$PW" > $UF/etc/system/local/user-seed.conf
  fi
  printf '[deployment-client]\n\n[target-broker:deploymentServer]\ntargetUri = 10.1.20.15:8089\n' > $UF/etc/system/local/deploymentclient.conf
  chown -R splunkfwd:splunkfwd $UF
  # read access to the sensor logs
  setfacl -R -m u:splunkfwd:rX /data/zeek /data/suricata 2>/dev/null || { apt-get -yq install acl; setfacl -R -m u:splunkfwd:rX /data/zeek /data/suricata; }
  setfacl -R -d -m u:splunkfwd:rX /data/zeek /data/suricata
  $UF/bin/splunk enable boot-start -systemd-managed 1 -user splunkfwd -group splunkfwd --accept-license --answer-yes --no-prompt
  systemctl start SplunkForwarder
  sleep 20
  systemctl is-active SplunkForwarder
  echo "uf OK"
}

stage_status() {
  echo "== $(hostname) $(lsb_release -ds) kernel $(uname -r)"
  ip -br addr; ip -br link show $CAP
  df -h / /data | sed 1d
  timedatectl show -p NTPSynchronized
  for s in capture-nic suricata zeek SplunkForwarder; do printf '%-18s %s\n' "$s" "$(systemctl is-active $s 2>/dev/null)"; done
  command -v suricata >/dev/null && suricata -V
  [ -x /opt/zeek/bin/zeek ] && /opt/zeek/bin/zeek --version && /opt/zeek/bin/zkg list 2>/dev/null
  ls -la /data/suricata /data/zeek/logs/current 2>/dev/null | head -n 30
}

case "${1:-}" in
  base) stage_base ;; suricata) stage_suricata; stage_extnet ;; extnet) stage_extnet ;; runsock) stage_runsock ;; zeek) stage_zeek ;; uf) shift; stage_uf "$@" ;; status) stage_status ;;
  *) echo "usage: $0 base|suricata|extnet|runsock|zeek|uf <deb>|status" >&2; exit 2 ;;
esac
