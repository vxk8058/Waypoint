// Client for the Waypoint FastAPI backend (backend/api/app.py).
// In dev, Vite proxies /auth and /api to http://localhost:8000 (see vite.config.ts),
// so the default base URL is same-origin. Set VITE_API_BASE_URL to call another host directly.

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "waypoint.session";

export interface User {
  user_id: string;
  email: string;
  display_name: string;
  first_name: string;
  last_name: string;
  profile_id: string;
}

interface Session {
  access_token: string;
  expires_at: string; // ISO timestamp
  user: User;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---------- session storage ----------

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (new Date(session.expires_at).getTime() <= Date.now()) {
      localStorage.removeItem(TOKEN_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

function writeSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable (private mode etc.): the session just won't persist
  }
}

export function getSessionUser(): User | null {
  return readSession()?.user ?? null;
}

// ---------- requests ----------

/** Fetch JSON from the backend, attaching the bearer token. A 401 clears the session. */
export async function apiFetch<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = readSession()?.access_token;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the Waypoint server. Is the backend running?", 0);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) writeSession(null);
    // FastAPI errors: { detail: string } or { detail: [{ msg, ... }] } for validation errors.
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : res.statusText;
    throw new ApiError(message || `Request failed (${res.status})`, res.status);
  }
  return data as T;
}

// ---------- auth ----------

export async function login(email: string, password: string): Promise<User> {
  const session = await apiFetch<Session>("/auth/login", { method: "POST", body: { email, password } });
  writeSession(session);
  return session.user;
}

/** Validates the stored token with the backend; returns null if there is no valid session. */
export async function fetchCurrentUser(): Promise<User | null> {
  if (!readSession()) return null;
  try {
    return await apiFetch<User>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function logout() {
  writeSession(null);
}
