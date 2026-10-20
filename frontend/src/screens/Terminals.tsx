import { useEffect, useState } from "react";
import { SEG_VAR } from "../lib/segments";
import type { TargetView } from "../lib/types";
import { Terminal } from "../components/Terminal";

export function Terminals({
  targets,
  openRequest,
}: {
  targets: TargetView[];
  openRequest: string | null;
}) {
  const openable = targets.filter(
    (t) => t.configured && t.access !== "power-only" && t.os !== "appliance",
  );
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [active, setActive] = useState<string | null>(null);

  function open(name: string) {
    setOpenTabs((prev) => (prev.includes(name) ? prev : [...prev, name]));
    setActive(name);
  }

  // The dashboard's "Terminal" button asks for a specific target.
  useEffect(() => {
    if (openRequest) open(openRequest);
  }, [openRequest]);
  function close(name: string) {
    setOpenTabs((prev) => prev.filter((n) => n !== name));
    setActive((a) => (a === name ? null : a));
  }

  return (
    <div>
      <h2 className="screen-title">Terminals</h2>
      <div className="row wrap" style={{ marginBottom: 10 }}>
        <span className="muted">Open:</span>
        {openable.map((t) => (
          <button key={t.name} onClick={() => open(t.name)}>
            {t.name}
          </button>
        ))}
      </div>

      {openTabs.length > 0 && (
        <>
          <div className="term-tabs">
            {openTabs.map((name) => {
              const seg = targets.find((t) => t.name === name)?.segment;
              return (
                <div
                  key={name}
                  className={`term-tab ${active === name ? "active" : ""}`}
                  style={{ ["--seg-color" as string]: seg ? SEG_VAR[seg] : "var(--border)" }}
                  onClick={() => setActive(name)}
                >
                  {name}
                  <span
                    className="muted"
                    style={{ marginLeft: 8 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      close(name);
                    }}
                  >
                    ✕
                  </span>
                </div>
              );
            })}
          </div>
          {/* keep every terminal mounted; just hide the inactive ones so sessions persist */}
          {openTabs.map((name) => (
            <div key={name} style={{ display: active === name ? "block" : "none" }}>
              <Terminal target={name} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}
