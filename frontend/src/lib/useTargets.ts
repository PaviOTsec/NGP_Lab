import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { TargetView } from "./types";

export interface TargetsState {
  list: TargetView[];
  loading: boolean;
  refresh: () => void;
  discover: () => void;
}

// Loads targets, polls reachability on an interval, and exposes a manual discover().
export function useTargets(active: boolean): TargetsState {
  const [list, setList] = useState<TargetView[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<number | null>(null);

  // The 10 s refresh carries reachability + sessions but not Hyper-V state; keep the last
  // discovered power state rather than blanking it on every poll.
  const refresh = useCallback(() => {
    if (!active) return;
    api
      .targets()
      .then((fresh) =>
        setList((prev) => {
          const old = new Map(prev.map((t) => [t.name, t]));
          return fresh.map((t) => ({
            ...t,
            power_state: t.power_state ?? old.get(t.name)?.power_state,
            uptime_seconds: t.uptime_seconds ?? old.get(t.name)?.uptime_seconds,
          }));
        }),
      )
      .catch(() => {});
  }, [active]);

  const discover = useCallback(() => {
    if (!active) return;
    setLoading(true);
    api
      .discover()
      .then((found) =>
        setList((prev) => {
          const old = new Map(prev.map((t) => [t.name, t]));
          return found.map((t) => ({ ...t, reachability: old.get(t.name)?.reachability ?? t.reachability }));
        }),
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [active]);

  useEffect(() => {
    if (!active) return;
    refresh();
    discover();
    timer.current = window.setInterval(refresh, 10_000); // REQUIREMENTS FR-06
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [active, refresh, discover]);

  return { list, loading, refresh, discover };
}
