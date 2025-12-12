import React, { useState } from "react";
import { endpoints } from "../lib/config";
import Logs from "./Logs";

export default function Executor() {
  const [code, setCode] = useState(`def calculate_sum(a, b):\n    return a + b\n`);
  const [runningId, setRunningId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function createAndRun() {
    setLoading(true);
    setError(null);
    setRunningId(null);

    try {
      // Create prebuilt code-review graph
      const createRes = await fetch(endpoints.createCodeReview(), { method: "POST" });
      if (!createRes.ok) {
        const text = await createRes.text().catch(() => "");
        throw new Error(`Create graph failed: ${createRes.status} ${text}`);
      }
      const createData = await createRes.json();
      const graph_id = createData.graph_id || createData.graphId || createData.id;

      // Run the graph
      const runRes = await fetch(endpoints.runGraph(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph_id, initial_state: { code } }),
      });

      if (!runRes.ok) {
        const txt = await runRes.text().catch(() => "");
        throw new Error(`Run failed: ${runRes.status} ${txt}`);
      }
      const runData = await runRes.json();
      setRunningId(runData.run_id || runData.runId || runData.runId);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Code Review — Executor</h2>
          <div className="small">Rule-based workflow</div>
        </div>

        <label className="small">Python code</label>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={10}
          style={{ width: "100%", marginTop: 8, fontFamily: "monospace" }}
        />

        {error && <div style={{ marginTop: 8, color: "crimson" }}>{error}</div>}

        <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn" onClick={createAndRun} disabled={loading}>
            {loading ? "Starting..." : "Create + Run Code Review"}
          </button>
          {runningId && (
            <div className="small">
              Run ID: <code>{runningId}</code>
            </div>
          )}
        </div>
      </div>

      {runningId && <Logs runId={runningId} />}
    </div>
  );
}
