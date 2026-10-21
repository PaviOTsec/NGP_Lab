import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { InventoryReview } from "../lib/types";

// inventory.yaml edited as text: its comments hold the observation history (pins, DRIFT notes),
// which a form would lose. The backend validates with the same model the loader uses, backs the
// file up, and reloads sessions on save.
export function Inventory({ focus, onSaved }: { focus: string | null; onSaved: () => void }) {
  const [path, setPath] = useState("");
  const [text, setText] = useState("");
  const [base, setBase] = useState({ text: "", sha: "" });
  const [review, setReview] = useState<InventoryReview | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const ta = useRef<HTMLTextAreaElement>(null);

  async function load() {
    const src = await api.inventorySource();
    // A textarea works in \n; the backend restores the file's own line endings on save.
    const lf = src.text.replace(/\r\n/g, "\n");
    setPath(src.path);
    setText(lf);
    setBase({ text: lf, sha: src.sha256 });
    setReview(null);
    setMsg("");
  }

  useEffect(() => {
    load().catch((e) => setMsg((e as Error).message));
  }, []);

  // Jump to the entry the dashboard's Edit button asked for.
  useEffect(() => {
    const el = ta.current;
    if (!focus || !el || !text) return;
    const esc = focus.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const m = new RegExp(`name:\\s*${esc}(?=[\\s,}])`).exec(text);
    if (!m) return;
    el.focus();
    el.setSelectionRange(m.index, m.index + m[0].length);
    const line = text.slice(0, m.index).split("\n").length - 1;
    el.scrollTop = Math.max(0, (line - 3) * parseFloat(getComputedStyle(el).lineHeight || "18"));
  }, [focus, base.sha]); // eslint-disable-line react-hooks/exhaustive-deps

  async function validate() {
    setBusy(true);
    try {
      setReview(await api.validateInventory(text));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.validateInventory(text);
      setReview(r);
      if (!r.ok) return;
      const lines = [
        `Save inventory.yaml and reload? Open sessions and terminals reconnect.`,
        r.added.length ? `Added: ${r.added.join(", ")}` : "",
        r.removed.length ? `Removed: ${r.removed.join(", ")}` : "",
        r.changed.length ? `Changed: ${r.changed.join(", ")}` : "",
        ...r.warnings.map((w) => `⚠ ${w}`),
      ].filter(Boolean);
      if (!r.added.length && !r.removed.length && !r.changed.length && text === base.text) {
        setMsg("No changes.");
        return;
      }
      if (!confirm(lines.join("\n"))) return;
      const res = await api.saveInventory(text, base.sha);
      await load();
      setMsg(`Saved. Backup: ${res.backup.split(/[\\/]/).pop()}`);
      onSaved();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const dirty = text !== base.text;

  return (
    <div>
      <div className="row">
        <h2 className="screen-title grow">Inventory</h2>
        <button onClick={validate} disabled={busy}>Validate</button>
        <button onClick={() => load()} disabled={busy || !dirty}>Revert</button>
        <button onClick={save} disabled={busy || !dirty}>Save &amp; reload</button>
      </div>
      <div className="muted mono" style={{ fontSize: 12, marginBottom: 8 }}>
        {path}{dirty ? " · unsaved changes" : ""}
      </div>
      <textarea
        ref={ta}
        className="mono inv-editor"
        spellCheck={false}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setReview(null);
        }}
      />
      {msg && <div className={msg.startsWith("Saved") || msg === "No changes." ? "muted" : "err"}>{msg}</div>}
      {review && (
        <div className="inv-review">
          {review.ok ? <div className="ok">Valid.</div> : review.errors.map((e, i) => <div key={i} className="err">{e}</div>)}
          {review.added.length > 0 && <div>Added: {review.added.join(", ")}</div>}
          {review.removed.length > 0 && <div>Removed: {review.removed.join(", ")}</div>}
          {review.changed.length > 0 && <div>Changed: {review.changed.join(", ")}</div>}
          {review.warnings.map((w, i) => <div key={i} className="warn">⚠ {w}</div>)}
        </div>
      )}
    </div>
  );
}
