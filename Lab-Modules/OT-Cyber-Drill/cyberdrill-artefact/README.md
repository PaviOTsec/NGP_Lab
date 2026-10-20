# CyberDrill Artefacts

Evidence captured while building and validating the OT Cyber Drill golden path. Each stage's real
command output / screenshot lands here and becomes the source material for the facilitator guide
(`OT_Cyber_Drill_Guide.docx`, to be produced). Trainer-only.

## Contents

| File | Stage | What it proves |
|---|---|---|
| `STAGE2_VALIDATION.md` | GP-0 → GP-2 | Range staging + the pass-the-hash → NMS chain is viable (recon evidence) |
| `STAGE2_PTH_CONFIRM.txt` | GP-1/GP-2 | **PASS** — live `nxc` pass-the-hash into NMS over SMB + WinRM (`Pwn3d!`) |

## Status

- 2026-10-20: Range origin staged (Kali 10.5.20.50 + domain-joined RAC), Stage-2 prerequisites
  validated by read-only recon, and the **pass-the-hash hop into NMS proven live** (SMB + WinRM
  `Pwn3d!`). Next: build the durable seed (privileged service account resident on RAC) and capture
  the full extract→PtH chain, then the GP-2 honeyfile on MaintServer.
