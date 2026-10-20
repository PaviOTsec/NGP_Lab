import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { ClipItem, TargetView } from "../lib/types";

// The console view of the shared clipboard:
//  - left: the same board page the VMs open (http://<MC01>:<clipboard_port>/b/<board>)
//  - right: actions that ride the lab sessions — push an item to a VM as a file (converted for
//    the VM's OS, checksum-verified), pull a file from a VM onto the board, type into a VM's
//    keyboard (logon screens, consoles, appliances).
export function Clipboard({
  targets,
  clipboardPort,
}: {
  targets: TargetView[];
  clipboardPort: number | null;
}) {
  const [board, setBoard] = useState("main");
  const [items, setItems] = useState<ClipItem[]>([]);
  const vms = targets.filter((t) => t.configured);
  const shellable = vms.filter((t) => t.access !== "power-only" && t.os !== "appliance");
  const typeable = vms.filter((t) => t.kind === "guest" || t.kind === "appliance");

  const boardUrl = clipboardPort
    ? `${window.location.protocol}//${window.location.hostname}:${clipboardPort}/b/${encodeURIComponent(board)}`
    : null;

  const refresh = () => api.clipList(board).then((r) => setItems(r.items)).catch(() => setItems([]));
  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 3000);
    return () => window.clearInterval(t);
  }, [board]);

  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <h2 className="screen-title grow" style={{ margin: 0 }}>Clipboard</h2>
        <span className="muted">board</span>
        <input value={board} onChange={(e) => setBoard(e.target.value.trim() || "main")} style={{ width: 120 }} />
        {boardUrl && (
          <a href={boardUrl} target="_blank" rel="noreferrer">open in new tab</a>
        )}
      </div>
      <div className="clip-layout">
        <div className="clip-frame">
          {boardUrl ? (
            <iframe title="Lab clipboard" src={boardUrl} />
          ) : (
            <div className="muted" style={{ padding: 20 }}>
              The VM-facing clipboard server is disabled (<span className="mono">[clipboard_server] enabled = false</span>).
            </div>
          )}
        </div>
        <div className="clip-actions">
          <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            VMs open <span className="mono">http://&lt;MC01 address&gt;:{clipboardPort ?? "8766"}/</span> in a browser,
            or fetch with curl / Invoke-WebRequest (see "Terminal commands" on each item).
          </div>
          <PushPanel board={board} items={items} targets={shellable} />
          <PullPanel board={board} targets={shellable} onPulled={refresh} />
          <TypePanel targets={typeable} />
        </div>
      </div>
    </div>
  );
}

function useStatus() {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const wrap = async (fn: () => Promise<string>) => {
    setMsg(null);
    try {
      setMsg({ ok: true, text: await fn() });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiError ? e.message : String(e) });
    }
  };
  const view = msg && (
    <div style={{ fontSize: 12, marginTop: 6, color: msg.ok ? "var(--status-ok)" : "var(--status-bad)" }}>
      {msg.text}
    </div>
  );
  return { wrap, view };
}

function PushPanel({ board, items, targets }: { board: string; items: ClipItem[]; targets: TargetView[] }) {
  const [itemId, setItemId] = useState("");
  const [target, setTarget] = useState("");
  const [path, setPath] = useState("");
  const [eol, setEol] = useState("auto");
  const [sanitize, setSanitize] = useState(false);
  const { wrap, view } = useStatus();
  const item = items.find((i) => i.id === itemId) ?? items[0];
  const t = targets.find((x) => x.name === target) ?? targets[0];

  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <h4 style={{ margin: "0 0 8px" }}>Send item to VM as a file</h4>
      <select className="full" value={item?.id ?? ""} onChange={(e) => setItemId(e.target.value)}>
        {items.map((i) => (
          <option key={i.id} value={i.id}>
            {i.id} · {i.kind === "file" ? i.name : (i.name || (i.text ?? "").split("\n")[0].slice(0, 40) || "text")}
          </option>
        ))}
      </select>
      <select className="full" value={t?.name ?? ""} onChange={(e) => setTarget(e.target.value)}>
        {targets.map((x) => <option key={x.name} value={x.name}>{x.name} ({x.os})</option>)}
      </select>
      <input className="full mono" placeholder="remote path (default: drop folder)" value={path}
             onChange={(e) => setPath(e.target.value)} />
      {item?.kind === "text" && (
        <div className="row wrap" style={{ fontSize: 12, marginBottom: 6 }}>
          <select value={eol} onChange={(e) => setEol(e.target.value)}>
            <option value="auto">line endings: match VM OS</option>
            <option value="keep">line endings: as stored</option>
            <option value="lf">line endings: LF</option>
            <option value="crlf">line endings: CRLF</option>
          </select>
          <label><input type="checkbox" checked={sanitize} onChange={(e) => setSanitize(e.target.checked)} /> fix Word characters</label>
        </div>
      )}
      <button
        className="primary"
        disabled={!item || !t}
        onClick={() =>
          wrap(async () => {
            const r = await api.pushToVM({
              target: t!.name, board, item_id: item!.id, remote_path: path || undefined, eol, sanitize,
            });
            return `${r.path} · ${r.bytes} bytes via ${r.transport} · sha256 verified`;
          })
        }
      >
        Send
      </button>
      {view}
    </div>
  );
}

function PullPanel({ board, targets, onPulled }: { board: string; targets: TargetView[]; onPulled: () => void }) {
  const [target, setTarget] = useState("");
  const [path, setPath] = useState("");
  const { wrap, view } = useStatus();
  const t = targets.find((x) => x.name === target) ?? targets[0];
  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <h4 style={{ margin: "0 0 8px" }}>Pull a file from VM onto the board</h4>
      <select className="full" value={t?.name ?? ""} onChange={(e) => setTarget(e.target.value)}>
        {targets.map((x) => <option key={x.name} value={x.name}>{x.name} ({x.os})</option>)}
      </select>
      <input className="full mono" placeholder={t?.os === "linux" ? "/etc/hosts" : "C:\\Windows\\System32\\drivers\\etc\\hosts"}
             value={path} onChange={(e) => setPath(e.target.value)} />
      <button
        disabled={!t || !path}
        onClick={() =>
          wrap(async () => {
            const r = await api.pullFromVM(t!.name, path, board);
            onPulled();
            return `posted as ${r.id} (${r.size} bytes)`;
          })
        }
      >
        Pull
      </button>
      {view}
    </div>
  );
}

function TypePanel({ targets }: { targets: TargetView[] }) {
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [cred, setCred] = useState("");
  const { wrap, view } = useStatus();
  const t = targets.find((x) => x.name === target) ?? targets[0];
  return (
    <div className="card">
      <h4 style={{ margin: "0 0 8px" }}>Type into VM keyboard</h4>
      <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>
        Works at logon screens and consoles. ASCII only, US layout; click into the VM's console first.
      </div>
      <select className="full" value={t?.name ?? ""} onChange={(e) => setTarget(e.target.value)}>
        {targets.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
      </select>
      <input className="full mono" placeholder="text to type" value={text} onChange={(e) => setText(e.target.value)} />
      <button
        disabled={!t || !text}
        onClick={() => wrap(async () => (await api.typeIntoVM(t!.name, text), `typed ${text.length} chars into ${t!.name}`))}
      >
        Type text
      </button>
      <input className="full mono" style={{ marginTop: 8 }} placeholder="credential entry name, e.g. np.local/Administrator"
             value={cred} onChange={(e) => setCred(e.target.value)} />
      <button
        disabled={!t || !cred}
        onClick={() => wrap(async () => (await api.typeIntoVM(t!.name, undefined, cred), `typed password of ${cred}`))}
      >
        Type password
      </button>
      {view}
    </div>
  );
}
