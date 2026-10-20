import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { LoadResult, SessionState } from "../lib/types";

// First screen: the operator chooses the credentials file — upload it from the browser, or
// name a path on MC01 (remembered for next launch). Loading it warms every session.
export function LoadCredentials({ onLoaded }: { onLoaded: (r: LoadResult) => void }) {
  const [state, setState] = useState<SessionState | null>(null);
  const [path, setPath] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    api.state().then((s) => {
      setState(s);
      setPath(s.last_credentials_path);
    });
  }, []);

  async function run(fn: () => Promise<LoadResult>) {
    setBusy(true);
    setErr(null);
    try {
      onLoaded(await fn());
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not reach the backend.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="unlock-wrap">
      <div className="unlock-card">
        <h1>
          Lab Console<span className="dot">.</span>
        </h1>
        <div className="sub">Choose the credentials file to connect to the lab.</div>

        {state && !state.inventory_exists && (
          <div className="err" style={{ marginBottom: 12 }}>
            No inventory at <span className="mono">{state.inventory_path}</span> — copy{" "}
            <span className="mono">config/inventory.example.yaml</span> there first.
          </div>
        )}

        <input
          ref={fileRef}
          type="file"
          accept=".yaml,.yml,.txt"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) run(() => api.loadFile(f));
          }}
        />
        <button className="primary" style={{ width: "100%" }} disabled={busy}
                onClick={() => fileRef.current?.click()}>
          {busy ? "Connecting…" : "Choose credentials file…"}
        </button>

        <div className="muted" style={{ fontSize: 12, margin: "14px 0 6px" }}>
          or load from a path on MC01 (remembered next time)
        </div>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (path.trim()) run(() => api.loadPath(path.trim()));
          }}
        >
          <input
            className="grow mono"
            style={{ marginBottom: 0, fontSize: 12 }}
            placeholder="C:\lab\credentials.yaml"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <button type="submit" disabled={busy || !path.trim()}>
            Load
          </button>
        </form>
        {err && <div className="err">{err}</div>}
        <div className="muted" style={{ fontSize: 11, marginTop: 14 }}>
          Format: see <span className="mono">config/credentials.example.yaml</span>
        </div>
      </div>
    </div>
  );
}
