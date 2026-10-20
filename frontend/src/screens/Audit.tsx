import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function Audit() {
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    api.audit().then((r) => setEvents(r.events.reverse()));
  }, []);

  return (
    <div>
      <h2 className="screen-title">Audit</h2>
      <table className="grid">
        <thead>
          <tr><th>Time</th><th>Action</th><th>Target</th><th>Transport</th><th>Result</th></tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={i}>
              <td className="mono">{String(e.ts ?? "")}</td>
              <td>{String(e.action ?? "")}</td>
              <td>{String(e.target ?? "")}</td>
              <td>{String(e.transport ?? "")}</td>
              <td>{String(e.result ?? "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
