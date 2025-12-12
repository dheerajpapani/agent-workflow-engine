import React from "react";
import Executor from "./components/Executor";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 20, maxWidth: 900, margin: "0 auto" }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Agent Workflow Engine — UI</h1>
        <p style={{ margin: "8px 0 0 0", color: "#666" }}>
          Minimal React UI — runs Code Review workflow on backend.
        </p>
      </header>

      <main>
        <Executor />
      </main>

      <footer style={{ marginTop: 40, color: "#888", fontSize: 13 }}>
        Backend: <code>{import.meta.env.VITE_API_BASE_URL}</code>
      </footer>
    </div>
  );
}
