import React, { useEffect, useState, useRef } from "react";
import { endpoints } from "../lib/config";

/**
 * Logs component
 * - Connects to WS endpoint for live log streaming
 * - Fetches persisted run state on mount and when WS sends "connected"
 * - Falls back to polling when WS closes/errors
 *
 * Props:
 *   runId: string
 */
export default function Logs({ runId }) {
  const [logs, setLogs] = useState([]); // array of { id, timestamp, message, type }
  const [status, setStatus] = useState("pending");
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    // Normalize raw backend log string into object
    const parseBackendLine = (line, idx = 0) => {
      // Expect format: "[2025-12-11T23:42:18.415674] Message..."
      const m = /^\[([^\]]+)\]\s*(.*)$/.exec(line);
      let ts = new Date().toISOString();
      let msg = line;
      if (m) {
        // Some timestamps may not be strictly parseable by Date; try to coerce
        try {
          const parsed = new Date(m[1]);
          if (!isNaN(parsed.getTime())) ts = parsed.toISOString();
        } catch {}
        msg = m[2];
      }
      return {
        id: `persisted-${idx}-${(msg || "").slice(0, 80)}`,
        timestamp: ts,
        message: msg,
        type: "info",
      };
    };

    // Fetch persisted state (logs + status)
    const fetchRunState = async () => {
      try {
        const res = await fetch(endpoints.graphState(runId));
        if (!res.ok) return;
        const data = await res.json();
        if (!mountedRef.current) return;

        // backend returns an array of log strings in data.logs
        const backendLogs =
          Array.isArray(data.logs) && data.logs.length > 0
            ? data.logs.map((line, i) => parseBackendLine(line, i))
            : [];

        // If we already have live logs (appended after connect), keep them and merge
        setLogs((prev) => {
          // keep only entries that were 'live' (id startsWith live-) and were added after fetch
          const live = prev.filter((p) => typeof p.id === "string" && p.id.startsWith("live-"));
          // Merge: persisted first, then live ones (avoid duplicate messages)
          const combined = [...backendLogs];
          for (const l of live) {
            if (!combined.find((c) => c.message === l.message && c.timestamp === l.timestamp)) {
              combined.push(l);
            }
          }
          // ensure chronological order (old->new)
          return combined.slice(-200);
        });

        if (data.status) setStatus(data.status);
      } catch (err) {
        // network or parse error — ignore, fallback to WS or polling
        // console.debug("fetchRunState error", err);
      }
    };

    // push a live message into state (keeps chronological order old->new)
    const pushLog = (message, type = "info") => {
      const item = {
        id: `live-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        timestamp: new Date().toISOString(),
        message,
        type,
      };
      setLogs((prev) => {
        const next = [...prev, item].slice(-200);
        return next;
      });
    };

    // Begin: fetch persisted logs first (so UI isn't empty), then open WS
    fetchRunState();

    // Setup WebSocket
    const wsUrl = endpoints.wsUrl(runId);
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
    } catch (e) {
      // If WS constructor fails, start polling fallback
      startPolling();
      return () => cleanup();
    }

    ws.onopen = () => {
      pushLog("[ws] connected", "info");
      // After connecting, fetch persisted state again to ensure we haven't missed anything
      fetchRunState();
    };

    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        // when backend sends connected event, refresh persisted logs (safe)
        if (payload.type === "connected") {
          // refresh persisted logs & status immediately
          fetchRunState();
          return;
        }

        if (payload.type === "keepalive") {
          // ignore keepalive messages
          return;
        }

        if (payload.type === "log" || payload.message) {
          // some messages are plain { type: "log", message: "..." }
          const msg = payload.message || JSON.stringify(payload);
          pushLog(msg, payload.level || payload.type || "info");
        }

        if (payload.type === "status" && payload.status) {
          setStatus(payload.status);
        }
      } catch (e) {
        // raw message not JSON; just append raw text
        pushLog(`[ws] ${String(ev.data)}`, "info");
      }
    };

    ws.onerror = (err) => {
      pushLog("[ws] error — switching to polling", "warning");
      startPolling();
    };

    ws.onclose = () => {
      pushLog("[ws] closed — switching to polling", "warning");
      startPolling();
    };

    // Polling fallback (called when WS fails/closes)
    let pollInterval = null;
    function startPolling() {
      if (pollInterval) return;
      // immediate poll
      (async () => {
        try {
          const res = await fetch(endpoints.graphState(runId));
          if (res.ok) {
            const d = await res.json();
            if (!mountedRef.current) return;
            setStatus(d.status || status);
            if (Array.isArray(d.logs)) {
              setLogs((prev) => {
                const live = prev.filter((p) => p.id && p.id.startsWith("live-"));
                const persisted = d.logs.map((line, i) => parseBackendLine(line, i));
                // merge unique: persisted first then live (preserve chronological)
                const merged = [...persisted];
                for (const l of live) {
                  if (!merged.find((m) => m.message === l.message && m.timestamp === l.timestamp)) {
                    merged.push(l);
                  }
                }
                return merged.slice(-200);
              });
            }
          }
        } catch (e) {
          // ignore network errors
        }
      })();

      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(endpoints.graphState(runId));
          if (!res.ok) return;
          const d = await res.json();
          if (!mountedRef.current) return;
          setStatus(d.status || status);
          if (Array.isArray(d.logs)) {
            setLogs((prev) => {
              const live = prev.filter((p) => p.id && p.id.startsWith("live-"));
              const persisted = d.logs.map((line, i) => parseBackendLine(line, i));
              const merged = [...persisted];
              for (const l of live) {
                if (!merged.find((m) => m.message === l.message && m.timestamp === l.timestamp)) {
                  merged.push(l);
                }
              }
              return merged.slice(-200);
            });
          }
        } catch (e) {
          // ignore
        }
      }, 1000);
    }

    function cleanup() {
      mountedRef.current = false;
      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.close();
      } catch (e) {}
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    }

    return () => {
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // Render
  return (
    <div className="card" style={{ marginTop: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div>
          <strong>Execution Logs</strong>
        </div>
        <div className="small">
          Status: <strong>{status}</strong>
        </div>
      </div>

      <div className="logs" style={{ maxHeight: 320, overflowY: "auto", fontFamily: "monospace", fontSize: 13 }}>
        {logs.length === 0 ? (
          <div style={{ opacity: 0.7 }}>Waiting for logs...</div>
        ) : (
          logs.map((l) => (
            <div
              key={l.id}
              style={{
                padding: "6px 8px",
                borderBottom: "1px solid rgba(0,0,0,0.06)",
                whiteSpace: "pre-wrap",
              }}
            >
              <div style={{ color: "var(--muted, #666)", fontSize: 11 }}>{new Date(l.timestamp).toLocaleTimeString()}</div>
              <div>{l.message}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
