# app/engine/state.py
from typing import Any, Optional
from datetime import datetime
from app.schemas.state import WorkflowState, RunStatus

class StateManager:
    def __init__(self, workflow_state: WorkflowState):
        self.state = workflow_state

    def update_data(self, updates: dict[str, Any]) -> None:
        self.state.state_data.update(updates)
        self.state.updated_at = datetime.utcnow()

    def set_current_node(self, node_id: Optional[str]) -> None:
        self.state.current_node = node_id
        self.state.updated_at = datetime.utcnow()

    def set_status(self, status: RunStatus) -> None:
        self.state.status = status
        self.state.updated_at = datetime.utcnow()

    def add_log(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        self.state.logs.append(f"[{timestamp}] {message}")

    def increment_iteration(self) -> bool:
        self.state.iteration_count += 1
        if self.state.iteration_count >= self.state.max_iterations:
            self.add_log(f"Max iterations ({self.state.max_iterations}) reached")
            return False
        return True

    def set_error(self, error: str) -> None:
        self.state.error = error
        self.state.status = RunStatus.FAILED
        self.add_log(f"ERROR: {error}")

    def get_data(self) -> dict[str, Any]:
        return self.state.state_data.copy()

    def get_value(self, key: str, default: Any = None) -> Any:
        return self.state.state_data.get(key, default)

    def is_running(self) -> bool:
        return self.state.status == RunStatus.RUNNING

    def to_response(self) -> dict[str, Any]:
        return {
            "run_id": self.state.run_id,
            "graph_id": self.state.graph_id,
            "status": self.state.status.value,
            "current_node": self.state.current_node,
            "state_data": self.state.state_data,
            "logs": self.state.logs,
            "iteration_count": self.state.iteration_count,
            "error": self.state.error,
        }
