import { useEffect, useRef } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { terminalWsUrl } from "../lib/api";

// One xterm instance bound to one target's WebSocket. Handles both PTY mode (SSH, full
// interactivity) and line mode (WinRM/PSRP, command-at-a-time) based on the server's "ready".
export function Terminal({ target }: { target: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const term = new XTerm({
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 13,
      theme: { background: "#04101f", foreground: "#e8eef6" },
      cursorBlink: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current!);
    fit.fit();

    const ws = new WebSocket(terminalWsUrl(target));
    let mode: "pty" | "line" = "pty";
    let lineBuf = "";

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "ready") {
        mode = msg.mode;
        term.writeln(
          mode === "line"
            ? `\x1b[90m[${target}] line mode (WinRM/PSRP) — type a command, Enter to run\x1b[0m`
            : `\x1b[90m[${target}] connected\x1b[0m`,
        );
        if (mode === "line") term.write("\r\n> ");
      } else if (msg.type === "data") {
        term.write(msg.data.replace(/\n/g, "\r\n"));
      } else if (msg.type === "exit") {
        term.write(`\x1b[90m[exit ${msg.code} · ${msg.ms}ms]\x1b[0m\r\n> `);
      } else if (msg.type === "error") {
        term.writeln(`\x1b[31m${msg.message}\x1b[0m`);
      }
    };
    ws.onclose = () => term.writeln("\r\n\x1b[90m[session closed]\x1b[0m");

    term.onData((data) => {
      if (mode === "pty") {
        ws.send(JSON.stringify({ type: "data", data }));
        return;
      }
      // line mode: local echo + buffer until Enter
      if (data === "\r") {
        ws.send(JSON.stringify({ type: "data", data: lineBuf }));
        term.write("\r\n");
        lineBuf = "";
      } else if (data === "\x7f") {
        if (lineBuf.length) {
          lineBuf = lineBuf.slice(0, -1);
          term.write("\b \b");
        }
      } else {
        lineBuf += data;
        term.write(data);
      }
    });

    term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN && mode === "pty") {
        ws.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    });

    // Refit whenever the container changes size — including when a hidden tab is shown.
    const ro = new ResizeObserver(() => {
      if (hostRef.current && hostRef.current.offsetWidth > 0) fit.fit();
    });
    ro.observe(hostRef.current!);

    return () => {
      ro.disconnect();
      ws.close();
      term.dispose();
    };
  }, [target]);

  return <div className="term-host" ref={hostRef} />;
}
