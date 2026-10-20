import { useEffect, useRef, useState } from "react";
import { api, ApiError, runFileUrl } from "../lib/api";
import type { PlaybookDef, RunDetail, RunEvent, RunSummary, StepRecord, TargetView } from "../lib/types";

const STATUS_COLOR: Record<string, string> = {
  ok: "var(--status-ok)",
  failed: "var(--status-bad)",
  running: "var(--status-warn)",
  cancelled: "var(--status-unknown)",
  skipped: "var(--status-unknown)",
  pending: "var(--border)",
};

function Status({ s }: { s: string }) {
  return (
    <span className="pill" style={{ color: STATUS_COLOR[s], borderColor: STATUS_COLOR[s] }}>
      {s}
    </span>
  );
}

export function Playbooks({ targets }: { targets: TargetView[] }) {
  const [books, setBooks] = useState<PlaybookDef[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<PlaybookDef | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const loadRuns = () => api.runs().then((r) => setRuns(r.runs)).catch(() => {});

  useEffect(() => {
    api.playbooks().then((r) => {
      setBooks(r.playbooks);
      setErrors(r.errors);
    });
    loadRuns();
  }, []);

  return (
    <div>
      <h2 className="screen-title">Playbooks</h2>
      {errors.length > 0 && (
        <div className="err" style={{ marginBottom: 10 }}>
          {errors.length} file(s) failed to load:
          <ul style={{ margin: "4px 0" }}>
            {errors.map((e) => (
              <li key={e} className="mono" style={{ fontSize: 12 }}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="pb-layout">
        <div className="pb-side">
          {books.map((b) => (
            <div
              key={b.name}
              className={`card ${selected?.name === b.name && !runId ? "selected" : ""}`}
              style={{ marginBottom: 8, cursor: "pointer" }}
              onClick={() => {
                setSelected(b);
                setRunId(null);
              }}
            >
              <div className="name">{b.title}</div>
              <div className="meta">{b.description}</div>
              <div className="muted" style={{ fontSize: 11 }}>
                {b.steps.length} step(s) · {b.matches.length} target(s)
              </div>
            </div>
          ))}

          <h3 className="side-h">Recent runs</h3>
          {runs.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No runs yet.</div>}
          {runs.map((r) => (
            <div
              key={r.id}
              className={`run-row ${runId === r.id ? "active" : ""}`}
              onClick={() => setRunId(r.id)}
              title={r.id}
            >
              <Status s={r.status} /> <span className="grow">{r.title}</span>
              <span className="muted mono" style={{ fontSize: 11 }}>{r.started.slice(5, 16).replace("T", " ")}</span>
            </div>
          ))}
        </div>

        <div className="grow" style={{ minWidth: 0 }}>
          {runId ? (
            <RunView runId={runId} onDone={loadRuns} />
          ) : selected ? (
            <Launcher
              key={selected.name}
              pb={selected}
              targets={targets}
              onStarted={(id) => {
                setRunId(id);
                loadRuns();
              }}
            />
          ) : (
            <div className="muted">
              Pick a playbook. Playbooks are YAML files in <span className="mono">playbooks/</span>;
              custom step types are Python files in <span className="mono">playbooks/modules/</span>.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Launcher({
  pb,
  targets,
  onStarted,
}: {
  pb: PlaybookDef;
  targets: TargetView[];
  onStarted: (runId: string) => void;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(pb.params.map((p) => [p.name, p.default ?? (p.type === "bool" ? false : "")])),
  );
  const [chosen, setChosen] = useState<Set<string>>(new Set(pb.matches));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const candidates = targets.filter((t) => t.configured);

  async function start() {
    if (pb.confirm && !confirm(`Run "${pb.title}" on ${chosen.size} target(s)?\n\n${[...chosen].join(", ")}`))
      return;
    setBusy(true);
    setErr(null);
    try {
      const run = await api.runPlaybook(pb.name, values, [...chosen]);
      onStarted(run.id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>{pb.title}</h3>
      <div className="muted" style={{ marginBottom: 12 }}>{pb.description}</div>

      <div className="pb-steps">
        {pb.steps.map((s, i) => (
          <span key={i} className="pill">
            {i + 1}. {s.name} <span className="muted">({s.module}{s.credential !== "default" ? `, ${s.credential}` : ""})</span>
          </span>
        ))}
      </div>

      {pb.params.length > 0 && <h4>Parameters</h4>}
      {pb.params.map((p) => (
        <div className="row" key={p.name} style={{ marginBottom: 8 }}>
          <label style={{ width: 240 }}>
            {p.label ?? p.name}
            {p.required && <span style={{ color: "var(--status-bad)" }}> *</span>}
          </label>
          {p.type === "bool" ? (
            <input
              type="checkbox"
              checked={Boolean(values[p.name])}
              onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.checked }))}
            />
          ) : p.type === "choice" ? (
            <select value={String(values[p.name] ?? "")}
                    onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}>
              {p.choices.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          ) : p.type === "text" ? (
            <textarea className="grow mono" rows={4} value={String(values[p.name] ?? "")}
                      onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))} />
          ) : (
            <input
              className="grow"
              type={p.type === "int" ? "number" : "text"}
              value={String(values[p.name] ?? "")}
              onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
            />
          )}
        </div>
      ))}

      <h4>
        Targets <span className="muted" style={{ fontWeight: 400 }}>({chosen.size} selected)</span>{" "}
        <button style={{ fontSize: 11, padding: "1px 6px" }} onClick={() => setChosen(new Set(pb.matches))}>
          matching
        </button>{" "}
        <button style={{ fontSize: 11, padding: "1px 6px" }} onClick={() => setChosen(new Set())}>
          none
        </button>
      </h4>
      <div className="row wrap" style={{ marginBottom: 14 }}>
        {candidates.map((t) => (
          <label key={t.name} className="pill" style={{ cursor: "pointer", opacity: pb.matches.includes(t.name) ? 1 : 0.6 }}>
            <input
              type="checkbox"
              checked={chosen.has(t.name)}
              onChange={() =>
                setChosen((prev) => {
                  const next = new Set(prev);
                  next.has(t.name) ? next.delete(t.name) : next.add(t.name);
                  return next;
                })
              }
              style={{ marginRight: 6 }}
            />
            {t.name}
          </label>
        ))}
      </div>

      <button className="primary" onClick={start} disabled={busy || chosen.size === 0}>
        {busy ? "Starting…" : `Run on ${chosen.size}`}
      </button>
      {err && <div className="err">{err}</div>}
    </div>
  );
}

function RunView({ runId, onDone }: { runId: string; onDone: () => void }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [open, setOpen] = useState<{ target: string; index: number } | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    let stop = false;
    let timer: number | undefined;
    seq.current = 0;
    setEvents([]);
    setOpen(null);
    const tick = async () => {
      try {
        const r = await api.run(runId, seq.current);
        if (stop) return;
        setRun(r);
        if (r.events.length) {
          seq.current = r.events[r.events.length - 1].seq;
          setEvents((prev) => [...prev, ...r.events]);
        }
        if (r.status === "running") timer = window.setTimeout(tick, 1000);
        else onDone();
      } catch {
        if (!stop) timer = window.setTimeout(tick, 3000);
      }
    };
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [runId]);

  if (!run) return <div className="muted">Loading run…</div>;
  const targetNames = Object.keys(run.targets);
  const stepNames = targetNames.length ? run.targets[targetNames[0]].steps.map((s) => s.name) : [];
  const openStep: StepRecord | undefined = open
    ? run.targets[open.target]?.steps[open.index - 1]
    : undefined;

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <h3 style={{ margin: 0 }} className="grow">
          {run.title} <Status s={run.status} />
        </h3>
        {run.status === "running" && (
          <button className="danger" onClick={() => api.cancelRun(run.id)}>Cancel</button>
        )}
      </div>
      <div className="muted mono" style={{ fontSize: 11, marginBottom: 12 }}>
        {run.id} · by {run.actor} · folder {run.dir}
      </div>

      <div style={{ overflowX: "auto" }}>
        <table className="grid run-grid">
          <thead>
            <tr>
              <th>Target</th>
              {stepNames.map((s, i) => <th key={i}>{i + 1}. {s}</th>)}
            </tr>
          </thead>
          <tbody>
            {targetNames.map((tn) => (
              <tr key={tn}>
                <td><Status s={run.targets[tn].status} /> {tn}</td>
                {run.targets[tn].steps.map((st) => (
                  <td
                    key={st.index}
                    className="step-cell"
                    style={{ borderLeft: `3px solid ${STATUS_COLOR[st.status]}` }}
                    onClick={() => setOpen({ target: tn, index: st.index })}
                    title="Show output"
                  >
                    <div style={{ color: STATUS_COLOR[st.status] }}>{st.status}</div>
                    {st.duration_ms > 0 && <div className="muted" style={{ fontSize: 11 }}>{(st.duration_ms / 1000).toFixed(1)}s {st.transport}</div>}
                    {st.error && <div className="err" style={{ fontSize: 11, marginTop: 2 }}>{st.error.slice(0, 80)}</div>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && openStep && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="row">
            <strong className="grow">{open.target} · {openStep.name}</strong>
            {openStep.log && <a href={runFileUrl(run.id, openStep.log)}>full log</a>}
            <button onClick={() => setOpen(null)}>Close</button>
          </div>
          {openStep.artifacts.length > 0 && (
            <div style={{ margin: "6px 0" }}>
              Artifacts:{" "}
              {openStep.artifacts.map((a) => (
                <a key={a} href={runFileUrl(run.id, a)} style={{ marginRight: 10 }} className="mono">{a}</a>
              ))}
            </div>
          )}
          <pre className="out">{openStep.output || "(no output)"}</pre>
          {openStep.stderr && <pre className="out err-out">{openStep.stderr}</pre>}
        </div>
      )}

      <h4>Events</h4>
      <div className="events mono">
        {events.slice().reverse().map((e) => (
          <div key={e.seq}>
            <span className="muted">{e.ts.slice(11, 19)}</span>{" "}
            <span style={{ color: STATUS_COLOR[e.status] ?? "var(--text-dim)" }}>{e.status}</span>{" "}
            {e.target && <b>{e.target}</b>} {e.step && <span className="muted">{e.step}:</span>} {e.message}
          </div>
        ))}
      </div>
    </div>
  );
}
