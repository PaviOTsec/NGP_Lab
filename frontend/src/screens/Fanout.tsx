import { useState } from "react";
import { api } from "../lib/api";
import type { FanoutResult, TargetView } from "../lib/types";

export function Fanout({ targets }: { targets: TargetView[] }) {
  const runnable = targets.filter((t) => t.configured && t.access !== "power-only");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [command, setCommand] = useState("");
  const [results, setResults] = useState<FanoutResult[]>([]);
  const [busy, setBusy] = useState(false);

  function toggle(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  async function run() {
    if (!command || selected.size === 0) return;
    setBusy(true);
    try {
      setResults(await api.fanout([...selected], command));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 className="screen-title">Fan-out</h2>
      <div className="row wrap" style={{ marginBottom: 10 }}>
        {runnable.map((t) => (
          <label key={t.name} className="pill" style={{ cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={selected.has(t.name)}
              onChange={() => toggle(t.name)}
              style={{ marginRight: 6 }}
            />
            {t.name}
          </label>
        ))}
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <input
          className="grow mono"
          placeholder="Command to run on every selected target"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button className="primary" onClick={run} disabled={busy || !command || selected.size === 0}>
          {busy ? "Running…" : `Run on ${selected.size}`}
        </button>
      </div>

      {results.length > 0 && (
        <table className="grid">
          <thead>
            <tr>
              <th>Target</th>
              <th>Transport</th>
              <th>Exit</th>
              <th>ms</th>
              <th>Output</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.target}>
                <td>{r.target}</td>
                <td>{r.transport}</td>
                <td style={{ color: r.error || r.exit_code ? "var(--status-bad)" : "var(--status-ok)" }}>
                  {r.error ? "err" : r.exit_code}
                </td>
                <td>{r.duration_ms}</td>
                <td>
                  <pre>{r.error ?? r.stdout}{r.stderr ? `\n${r.stderr}` : ""}</pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
