// Runtime configuration. Vite inlines VITE_* envs at build time.
// VITE_API_KEY must be set explicitly — no hardcoded fallback so a
// misconfigured build fails visibly rather than silently shipping a known key.
const env = import.meta.env as Record<string, string | undefined>;

export const API_BASE = env.VITE_API_BASE ?? 'http://localhost:8000';
export const AI_BASE = env.VITE_AI_BASE ?? 'http://localhost:8001';
export const API_KEY = env.VITE_API_KEY ?? '';

export const WS_URL =
  env.VITE_WS_URL ?? API_BASE.replace(/^http/, 'ws') + '/ws/live';

/** True when the build was produced without an explicit API key. */
export const API_KEY_MISSING = API_KEY === '';

export const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'NIFTY'] as const;

const authHeaders = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function quoteCcy(symbol: string): string {
  return symbol.includes('USDT') ? 'USDT' : 'INR';
}
