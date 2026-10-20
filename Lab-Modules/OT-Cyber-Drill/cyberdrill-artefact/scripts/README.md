# CyberDrill Scripts

Reusable build/validation scripts for the drill, kept with the evidence so the guide can compile
from them. **None contains a secret** — they read from the credential store or generate passwords at
runtime and never print them. Run from the repo root with the backend venv, e.g.:

```
.\backend\.venv\Scripts\python -I Lab-Modules\OT-Cyber-Drill\cyberdrill-artefact\scripts\<name>.py backend
```

| Script | Stage | What it does | Change? |
|---|---|---|---|
| `join_rac_domain.py` | GP-0 setup | Join RAC to np.local (DNS→DC, join, reboot, verify). Flags: `--join --restart --verify` | yes (done) |
| `kali_probe.py` | GP-0 | First-contact SSH probe of Kali: pin host key, confirm reach + attacker tooling | read-only |
| `kali_reach.py` | recon | From Kali, targeted reachability to RAC/DC/MSSQL/INS on golden-path ports | read-only |
| `kali_reach_nms.py` | GP-2 | From Kali, reachability to NMS/MaintServer | read-only |
| `rac_recon.ps1` | GP-0/1 | RAC posture: local admins, AV/EDR, LSA Protection, Credential Guard (run via `remote_ps.py`) | read-only |
| `pth_nms_test.py` | GP-1/2 | Compute DA NT hash on MC01, prove pass-the-hash into NMS from Kali (`Pwn3d!`) | auth test |
| `build_seed.py` | GP-0 seed | Create `np\svc_backup` (Domain Admin) on the DC + resident scheduled task on RAC; store pw in creds | yes |

Helper used: `tools/nms-onboarding/remote_ps.py` (runs a read-only PS file on an inventory target via
the identity-checked session pool).
