# app/storage/memory.py
from typing import Any, Optional
from datetime import datetime
from app.schemas.state import WorkflowState

class InMemoryStorage:
    def __init__(self):
        self._graphs: dict[str, dict[str, Any]] = {}
        self._runs: dict[str, dict[str, Any]] = {}
        self._states: dict[str, WorkflowState] = {}

    async def save_graph(self, graph_id: str, graph_data: dict[str, Any]) -> str:
        graph_data["created_at"] = datetime.utcnow().isoformat()
        self._graphs[graph_id] = graph_data
        return graph_id

    async def get_graph(self, graph_id: str) -> Optional[dict[str, Any]]:
        return self._graphs.get(graph_id)

    async def delete_graph(self, graph_id: str) -> bool:
        if graph_id in self._graphs:
            del self._graphs[graph_id]
            return True
        return False

    async def save_run(self, run_id: str, run_data: dict[str, Any]) -> str:
        run_data["created_at"] = datetime.utcnow().isoformat()
        self._runs[run_id] = run_data
        return run_id

    async def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        return self._runs.get(run_id)

    async def save_run_state(self, run_id: str, state: WorkflowState) -> None:
        self._states[run_id] = state
        if run_id in self._runs:
            self._runs[run_id]["status"] = state.status.value
            self._runs[run_id]["updated_at"] = datetime.utcnow().isoformat()

    async def get_run_state(self, run_id: str) -> Optional[WorkflowState]:
        return self._states.get(run_id)

    async def list_graphs(self) -> list[dict[str, Any]]:
        return list(self._graphs.values())

    async def list_runs(self, graph_id: str = None) -> list[dict[str, Any]]:
        runs = list(self._runs.values())
        if graph_id:
            runs = [r for r in runs if r.get("graph_id") == graph_id]
        return runs

memory_storage = InMemoryStorage()
