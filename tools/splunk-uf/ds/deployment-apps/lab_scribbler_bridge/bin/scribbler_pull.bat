@echo off
rem Scribbler -> Splunk bridge: UF scripted input wrapper (see scribbler_pull.ps1).
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0scribbler_pull.ps1"
