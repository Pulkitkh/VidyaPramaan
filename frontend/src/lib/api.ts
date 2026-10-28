export type Role = "AICTE_ADMIN" | "INSTITUTION_ADMIN" | "VERIFIER" | "STUDENT" | "AUDITOR" | "REGULATOR" | "UNIVERSITY";

export interface User {
  username: string;
  role: Role;
  display_name: string;
  institution_id: number | null;
  student_id: number | null;
  org: string | null;
  university: string | null;
  state: string | null;
}

export interface Finding {
  code: string;
  severity: "ERROR" | "WARNING" | "INFO";
  title: string;
  message: string;
  evidence: Record<string, unknown>;
  rule_version: string;
}

export interface RowResult {
  row_no: number;
  status: "OK" | "WARNING" | "ERROR";
  data: Record<string, string | number | boolean | null>;
  programme_id: number | null;
  is_update: boolean;
  changes?: { field: string; old: unknown; new: unknown }[];
  findings: Finding[];
}

export interface Batch {
  id: number;
  filename: string;
  source: string;
  uploaded_by: string;
  created_at: string;
  status: string;
  total_rows: number;
  error_rows: number;
  warning_rows: number;
  committed_rows: number;
  rows?: RowResult[];
  column_map?: { renamed?: Record<string, string>; ignored?: string[] };
  rejected_at_commit?: number;
  changed_since_validation?: number[];
  created?: number;
  updated?: number;
  unchanged?: number;
  scan?: { findings: number; by_rule: Record<string, number> };
}

export interface Reason { feature: string; value: number; peer_median: number | null; z: number | null; text: string; peers?: string | null; rule?: string }

export interface LedgerRow {
  programme_id: number;
  code: string;
  name: string;
  level: string;
  approved_intake: number;
  within_intake: number;
  excess: number;
  utilisation: number;
  supernumerary: Record<string, { used: number; cap: number }>;
}

export interface StoredFinding {
  id: number;
  institution_id: number;
  institution: string | null;
  related_institution_id: number | null;
  related_institution: string | null;
  enrolment_id: number | null;
  batch_id: number | null;
  source: string;
  rule_code: string;
  severity: "ERROR" | "WARNING" | "INFO";
  message: string;
  evidence: Record<string, unknown>;
  rule_version: string;
  status: string;
  resolution_note: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  created_at: string;
}

const TOKEN_KEY = "vp_token";
const USER_KEY = "vp_user";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch { return null; }
}

export function storeSession(token: string | null, user: User | null) {
  try {
    if (token && user) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
  } catch { /* storage unavailable: session lives in memory only */ }
  memoryToken = token;
}

let memoryToken: string | null = getToken();

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = unknown>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  const token = memoryToken ?? getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(path, { ...opts, headers, body });
  if (res.status === 401 && token && !path.startsWith("/api/auth/")) {
    storeSession(null, null); // expired or invalid session: back to sign-in
    if (window.location.pathname !== "/login") window.location.assign("/login");
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* non-JSON error */ }
    throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

/** Fetch a protected file with the Authorization header (no token in the URL) and hand it to the browser. */
export async function download(path: string, filename?: string, open = false): Promise<void> {
  const token = memoryToken ?? getToken();
  const res = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const name = filename ?? /filename=([^;]+)/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "download";
  if (open) {
    const w = window.open(url, "_blank", "noopener");
    if (w) { window.setTimeout(() => URL.revokeObjectURL(url), 60_000); return; }
  }
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export const fmt = {
  int: (n: number | undefined | null) => (n ?? 0).toLocaleString("en-IN"),
  pct: (n: number | undefined | null, d = 1) => `${((n ?? 0) * 100).toFixed(d)}%`,
  date: (s: string | undefined | null) => (s ? new Date(s).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—"),
  dateTime: (s: string | undefined | null) => (s ? new Date(s).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"),
};
