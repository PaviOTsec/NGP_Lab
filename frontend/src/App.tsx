import { useEffect, useState } from "react";
import { api, ApiError } from "./lib/api";
import { LoadCredentials } from "./screens/LoadCredentials";
import { Dashboard } from "./screens/Dashboard";
import { Terminals } from "./screens/Terminals";
import { Fanout } from "./screens/Fanout";
import { Clipboard } from "./screens/Clipboard";
import { Playbooks } from "./screens/Playbooks";
import { Audit } from "./screens/Audit";
import { useTargets } from "./lib/useTargets";
import type { SessionState } from "./lib/types";

type Screen = "dashboard" | "terminals" | "fanout" | "playbooks" | "clipboard" | "audit";

const NAV: { id: Screen; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "terminals", label: "Terminals" },
  { id: "fanout", label: "Fan-out" },
  { id: "playbooks", label: "Playbooks" },
  { id: "clipboard", label: "Clipboard" },
  { id: "audit", label: "Audit" },
];

export function App() {
  const [state, setState] = useState<SessionState | null>(null);
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [termTarget, setTermTarget] = useState<string | null>(null);
  const ready = state?.ready === true;
  const targets = useTargets(ready);

  const refreshState = () =>
    api
      .state()
      .then(setState)
      .catch(() => setState(null));

  useEffect(() => {
    refreshState();
  }, []);

  // A 423 from any screen means the credentials were unloaded underneath us.
  useEffect(() => {
    const handler = (e: PromiseRejectionEvent) => {
      if (e.reason instanceof ApiError && e.reason.notReady) refreshState();
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  if (state === null) return <div className="unlock-wrap">Connecting to the backend…</div>;
  if (!ready) return <LoadCredentials onLoaded={() => refreshState()} />;

  return (
    <div className="app">
      <nav className="nav">
        <div className="brand">
          Lab Console<span className="dot">.</span>
        </div>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={screen === n.id ? "active" : ""}
            onClick={() => setScreen(n.id)}
          >
            {n.label}
          </button>
        ))}
        <div className="spacer" />
        <div className="nav-foot" title={state.credentials_source}>
          creds: {state.credentials_source.split(/[\\/]/).pop()}
        </div>
        <button
          className="lock"
          onClick={async () => {
            await api.unload();
            refreshState();
          }}
        >
          Disconnect
        </button>
      </nav>
      <main className="main">
        {screen === "dashboard" && (
          <Dashboard
            targets={targets}
            onOpenTerminal={(name) => {
              setTermTarget(name);
              setScreen("terminals");
            }}
          />
        )}
        {/* Terminals stay mounted so sessions survive switching screens. */}
        <div style={{ display: screen === "terminals" ? "block" : "none" }}>
          <Terminals targets={targets.list} openRequest={termTarget} />
        </div>
        {screen === "fanout" && <Fanout targets={targets.list} />}
        {screen === "playbooks" && <Playbooks targets={targets.list} />}
        {screen === "clipboard" && (
          <Clipboard targets={targets.list} clipboardPort={state.clipboard_port} />
        )}
        {screen === "audit" && <Audit />}
      </main>
    </div>
  );
}
