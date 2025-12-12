// frontend/src/lib/config.js
// Central config for frontend API endpoints.
// Use VITE_API_BASE_URL at build time or fallback to window.location.origin at runtime.

const VITE_API_BASE = import.meta.env?.VITE_API_BASE_URL || null;

/**
 * Derive the backend base URL.
 * - If VITE_API_BASE set (build-time), use it.
 * - Else derive from current window.location (runtime) so deployed app uses same origin.
 */
const API_BASE = VITE_API_BASE || (typeof window !== "undefined" ? window.location.origin : "http://localhost:8080");

function wsUrlForBase(base, runId) {
  try {
    const url = new URL(base);
    const proto = url.protocol === "https:" ? "wss:" : "ws:";
    // use host part only (host includes hostname:port)
    return `${proto}//${url.host}/ws/${runId}`;
  } catch (e) {
    // fallback
    return `ws://localhost:8080/ws/${runId}`;
  }
}

export const endpoints = {
  createCodeReview: () => `${API_BASE}/graph/create/code-review`,
  runGraph: () => `${API_BASE}/graph/run`,
  graphState: (runId) => `${API_BASE}/graph/state/${runId}`,
  wsUrl: (runId) => wsUrlForBase(API_BASE, runId),
};

// also export raw base for debugging
export const API = {
  base: API_BASE,
};
