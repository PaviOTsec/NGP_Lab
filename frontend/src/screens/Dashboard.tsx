import { api } from "../lib/api";
import { SEG_LABEL, SEG_VAR, SEGMENTS } from "../lib/segments";
import type { Reachability, TargetView } from "../lib/types";
import type { TargetsState } from "../lib/useTargets";

function stateClass(s?: string | null) {
  switch ((s ?? "").toLowerCase()) {
    case "running": return "state-running";
    case "off": return "state-off";
    case "saved": return "state-saved";
    case "paused": return "state-paused";
    default: return "state-unknown";
  }
}

function Chips({ r }: { r: Reachability }) {
  const items: [string, boolean | null][] = [
    ["WinRM", r.winrm], ["SSH", r.ssh], ["SMB", r.smb], ["RDP", r.rdp], ["443", r.https],
  ];
  return (
    <div className="chips">
      {items.filter(([, v]) => v !== null).map(([label, v]) => (
        <span key={label} className={`chip ${v ? "ok" : "bad"}`}>{label}</span>
      ))}
    </div>
  );
}

function Card({ t, onOpenTerminal }: { t: TargetView; onOpenTerminal: (name: string) => void }) {
  const isVM = t.kind === "guest" || t.kind === "appliance";
  const hasShell = t.configured && t.access !== "power-only" && t.os !== "appliance";
  const isField = t.kind === "field";

  async function checkpoint() {
    // Offer Production only if VSS is healthy; otherwise fall back to Standard.
    let type = "Production";
    try {
      const v = await api.vss(t.name);
      if (!v.vss_healthy) type = "Standard";
    } catch { type = "Standard"; }
    if (!confirm(`Create a ${type} checkpoint of ${t.name}?`)) return;
    try {
      const res = await api.checkpoint(t.name, type);
      alert(`Checkpoint created: ${res.name} (${res.snapshot_type})`);
    } catch (e) {
      alert(`Checkpoint failed: ${(e as Error).message}`);
    }
  }

  async function power(action: string) {
    if (t.ot) {
      // Handle with care: an OT VM may be serving a live process; make the operator name it.
      const typed = prompt(
        `${t.name} is an OT system (${t.segment}). Stopping it can interrupt a running process.\n` +
        `Type ${t.name} to ${action}:`,
      );
      if (typed !== t.name) return;
    }
    if (action === "turnoff" && !confirm(`Turn OFF ${t.name}? This is a hard power-off.`)) return;
    if (action === "shutdown" && !confirm(`Shut down ${t.name} (guest OS shutdown)?`)) return;
    try {
      const res = await api.power(t.name, action);
      alert(`${t.name}: ${res.state}`);
    } catch (e) {
      alert(`Action failed: ${(e as Error).message}`);
    }
  }

  return (
    <div className={`card ${t.configured || isField ? "" : "not-configured"}`}>
      <div className="head">
        <span className={`state-dot ${stateClass(t.power_state)}`} title={t.power_state ?? "unknown"} />
        <span className="name">{t.name}</span>
        {t.ot && <span className="badge-ot" title="L2 and below: handle with care">OT</span>}
        <span className="addr">{t.address || "—"}</span>
      </div>
      <div className="meta">
        {t.vendor ?? t.os} · {t.kind}
        {t.power_state ? ` · ${t.power_state}` : ""}
        {t.access === "power-only" ? " · power-only" : ""}
        {t.session?.state === "open" ? ` · ${t.session.transport}` : ""}
      </div>
      {isField ? (
        <div className="meta">{t.tags.join(" · ")} · not polled, hands-off</div>
      ) : (
        <Chips r={t.reachability} />
      )}
      {t.session?.state === "failed" && (
        <div className="err" style={{ fontSize: 11, marginTop: 4 }} title={t.session.detail}>
          {t.session.detail.slice(0, 120)}
        </div>
      )}
      <div className="actions">
        {hasShell && <button onClick={() => onOpenTerminal(t.name)}>Terminal</button>}
        {isVM && t.kind !== "appliance" && !t.ot && <button onClick={checkpoint}>Checkpoint</button>}
        {isVM && <button onClick={() => power("start")}>Start</button>}
        {isVM && <button onClick={() => power("shutdown")}>Shut down</button>}
        {isVM && <button className="danger" onClick={() => power("turnoff")}>Turn off</button>}
        {t.web_ui && (
          <button onClick={() => window.open(t.web_ui!, "_blank")}>Web UI</button>
        )}
      </div>
    </div>
  );
}

export function Dashboard({
  targets,
  onOpenTerminal,
}: {
  targets: TargetsState;
  onOpenTerminal: (name: string) => void;
}) {
  return (
    <div>
      <div className="row">
        <h2 className="screen-title grow">Dashboard</h2>
        <button
          onClick={() => api.reconnect().then(targets.refresh)}
          title="Retry sessions to targets that were down"
        >
          Reconnect
        </button>
        <button onClick={targets.discover} disabled={targets.loading}>
          {targets.loading ? "Discovering…" : "Refresh"}
        </button>
      </div>
      {SEGMENTS.map((seg) => {
        const inSeg = targets.list.filter((t) => t.segment === seg);
        if (inSeg.length === 0) return null;
        return (
          <div className="lane" key={seg} style={{ ["--seg-color" as string]: SEG_VAR[seg] }}>
            <h3>{SEG_LABEL[seg]}</h3>
            {(seg === "L2" || seg === "L1") && (
              <div className="lane-note">
                OT: handle with care. Observe first, one device at a time, back up before any change.
              </div>
            )}
            <div className="cards">
              {inSeg.map((t) => (
                <Card key={t.name} t={t} onOpenTerminal={onOpenTerminal} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
