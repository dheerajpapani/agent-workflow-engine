# app/schemas/state.py
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime
from enum import Enum

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class WorkflowState(BaseModel):
    run_id: str
    graph_id: str
    status: RunStatus = RunStatus.PENDING
    current_node: Optional[str] = None
    state_data: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 100
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None

class StateResponse(BaseModel):
    run_id: str
    graph_id: str
    status: str
    current_node: Optional[str]
    state_data: dict[str, Any]
    logs: list[str]
    iteration_count: int
    error: Optional[str]
