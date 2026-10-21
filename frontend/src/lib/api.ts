// Thin API client. The launch token comes from the ?token=... URL param the backend prints
// at startup; it's kept in sessionStorage so navigation keeps it, and attached to every call
// (header for HTTP, query param for the terminal WebSocket).

import type {
  ClipItem,
  FanoutResult,
  InventoryReview,
  InventorySource,
  LoadResult,
  PlaybookDef,
  RunDetail,
  RunSummary,
  SessionState,
  SessionStatus,
  TargetView,
} from "./types";

const TOKEN_KEY = "labconsole.token";

export function captureToken(): string | null {
  const url = new URL(window.location.href);
  const fromUrl = url.searchParams.get("token");
  if (fromUrl) {
    sessionStorage.setItem(TOKEN_KEY, fromUrl);
    // strip it from the address bar so it isn't shoulder-surfed / bookmarked
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.toString());
    return fromUrl;
  }
  return sessionStorage.getItem(TOKEN_KEY);
}

function token(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? "";
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const isForm = opts.body instanceof FormData;
  const res = await fetch(path, {
    ...opts,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      "X-LabConsole-Token": token(),
      ...(opts.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
  /** 423: credentials are not loaded (unloaded underneath us). */
  get notReady() {
    return this.status === 423;
  }
}

export const api = {
  token,

  // --- credentials / session ---
  state: () => req<SessionState>("/api/session/state"),
  loadFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<LoadResult>("/api/session/load-file", { method: "POST", body: fd });
  },
  loadPath: (path: string, remember = true) =>
    post<LoadResult>("/api/session/load-path", { path, remember }),
  unload: () => post<{ ready: boolean }>("/api/session/unload"),
  reconnect: () => post<SessionStatus[]>("/api/session/reconnect"),

  // --- inventory ---
  targets: () => req<TargetView[]>("/api/inventory/targets"),
  discover: () => post<TargetView[]>("/api/inventory/discover"),
  inventorySource: () => req<InventorySource>("/api/inventory/source"),
  validateInventory: (text: string) => post<InventoryReview>("/api/inventory/validate", { text }),
  saveInventory: (text: string, base_sha256: string) =>
    req<InventoryReview & { backup: string; sessions: SessionStatus[] }>("/api/inventory/source", {
      method: "PUT",
      body: JSON.stringify({ text, base_sha256 }),
    }),
  checkpoints: (name: string) =>
    req<{ name: string; snapshot_type: string }[]>(
      `/api/inventory/checkpoints/${encodeURIComponent(name)}`,
    ),

  fanout: (targets: string[], command: string) =>
    post<FanoutResult[]>("/api/fanout", { targets, command }),

  // --- hyper-v ---
  power: (target: string, action: string) =>
    post<{ target: string; state: string }>("/api/hyperv/power", { target, action }),
  checkpoint: (target: string, checkpoint_type: string, name?: string) =>
    post<{ target: string; name: string; snapshot_type: string }>("/api/hyperv/checkpoint", {
      target,
      checkpoint_type,
      name,
    }),
  vss: (target: string) =>
    req<{ target: string; vss_healthy: boolean }>(`/api/hyperv/vss/${encodeURIComponent(target)}`),

  // --- clipboard board (same store the VMs see) + session-backed helpers ---
  clipList: (board = "main") =>
    req<{ board: string; version: number; items: ClipItem[] }>(
      `/api/clip/${encodeURIComponent(board)}`,
    ),
  typeIntoVM: (target: string, text?: string, credential?: string) =>
    post<{ target: string; typed: boolean }>("/api/vmtext/type", { target, text, credential }),
  pushToVM: (body: {
    target: string;
    board: string;
    item_id?: string;
    remote_path?: string;
    eol?: string;
    sanitize?: boolean;
  }) =>
    post<{ path: string; bytes: number; sha256: string; transport: string; verified: boolean }>(
      "/api/vmtext/push",
      body,
    ),
  pullFromVM: (target: string, remote_path: string, board = "main") =>
    post<ClipItem>("/api/vmtext/pull", { target, remote_path, board }),

  // --- playbooks ---
  playbooks: () => req<{ playbooks: PlaybookDef[]; errors: string[] }>("/api/playbooks"),
  runPlaybook: (name: string, params: Record<string, unknown>, targets?: string[]) =>
    post<RunSummary>("/api/playbooks/run", { name, params, targets }),
  runs: () => req<{ runs: RunSummary[] }>("/api/playbooks/runs"),
  run: (id: string, since = 0) =>
    req<RunDetail>(`/api/playbooks/runs/${encodeURIComponent(id)}?since=${since}`),
  cancelRun: (id: string) =>
    post<{ cancelled: boolean }>(`/api/playbooks/runs/${encodeURIComponent(id)}/cancel`),

  audit: (limit = 200) => req<{ events: Record<string, unknown>[] }>(`/api/audit?limit=${limit}`),
};

/** Download URL for a run log/artifact (token in the query, since it's a plain link). */
export function runFileUrl(runId: string, rel: string): string {
  return `/api/playbooks/runs/${encodeURIComponent(runId)}/files/${rel
    .split("/")
    .map(encodeURIComponent)
    .join("/")}?token=${encodeURIComponent(token())}`;
}

// WebSocket URL for a terminal, with the token as a query param.
export function terminalWsUrl(target: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/terminals/ws/${encodeURIComponent(
    target,
  )}?token=${encodeURIComponent(token())}`;
}
