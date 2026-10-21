// Mirrors the backend's pydantic models / route payloads. Kept in sync by hand.

export type TransportName = "winrm" | "ssh" | "smb" | "psdirect" | "none";
export type ConnState =
  | "pending" | "connecting" | "open" | "failed" | "reconnecting" | "closed";
export type Segment = "L5" | "L4" | "DMZ" | "L3" | "Plantbus" | "L2" | "L1" | "Mgmt";
export type OS = "windows" | "linux" | "appliance" | "network";
export type Kind = "hypervisor" | "guest" | "appliance" | "network" | "baremetal" | "field";
export type Access = "full" | "ssh-web" | "power-only";

export interface Reachability {
  winrm: boolean | null;
  ssh: boolean | null;
  smb: boolean | null;
  rdp: boolean | null;
  https: boolean | null;
}

export interface SessionStatus {
  target: string;
  transport: TransportName;
  state: ConnState;
  detail: string;
}

export interface SessionState {
  ready: boolean;
  credentials_source: string;
  last_credentials_path: string;
  inventory_path: string;
  inventory_exists: boolean;
  clipboard_port: number | null;
}

export interface LoadResult {
  ready: boolean;
  credentials_source: string;
  entries: number;
  sessions: SessionStatus[];
}

export interface CheckpointInfo {
  name: string;
  snapshot_type: string;
  created_at?: string | null;
}

export interface TargetView {
  name: string;
  kind: Kind;
  os: OS;
  segment: Segment;
  address: string;
  route: "direct" | "via-host" | "via-jump";
  access: Access;
  configured: boolean;
  web_ui?: string | null;
  vendor?: string | null;
  tags: string[];
  ot: boolean; // L2 and below: handle with care
  power_state?: string | null;
  uptime_seconds?: number | null;
  guest_ips: string[];
  checkpoints: CheckpointInfo[];
  reachability: Reachability;
  session?: SessionStatus | null;
}

export interface FanoutResult {
  target: string;
  transport: TransportName;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  error?: string | null;
}

// --- playbooks ---

export interface PlaybookParam {
  name: string;
  type: string;
  default?: unknown;
  label?: string | null;
  choices: string[];
  required: boolean;
}

export interface PlaybookDef {
  name: string;
  title: string;
  description: string;
  confirm: boolean;
  params: PlaybookParam[];
  steps: { name: string; module: string; credential: string }[];
  matches: string[];
  source_file: string;
}

export type RunStatus = "running" | "ok" | "failed" | "cancelled";
export type StepStatus = "pending" | "running" | "ok" | "failed" | "skipped" | "cancelled";

export interface RunSummary {
  id: string;
  playbook: string;
  title: string;
  status: RunStatus;
  started: string;
  finished: string;
  actor: string;
  targets: Record<string, number>;
}

export interface StepRecord {
  index: number;
  name: string;
  module: string;
  status: StepStatus;
  started: string;
  duration_ms: number;
  transport: string;
  exit_code: number | null;
  output: string;
  stderr: string;
  error: string;
  artifacts: string[];
  log: string;
}

export interface RunEvent {
  seq: number;
  ts: string;
  target: string | null;
  step: string | null;
  status: string;
  message: string;
}

export interface RunDetail {
  id: string;
  playbook: string;
  title: string;
  params: Record<string, unknown>;
  actor: string;
  dir: string;
  status: RunStatus;
  started: string;
  finished: string;
  targets: Record<string, { target: string; status: string; steps: StepRecord[] }>;
  events: RunEvent[];
}

// --- clipboard board ---

export interface ClipItem {
  id: string;
  kind: "text" | "file";
  created: string;
  size: number;
  sha256: string;
  name: string;
  eol: string;
  suspicious: number;
  lines: number;
  origin: string;
  text?: string;
}
