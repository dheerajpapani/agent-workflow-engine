# app/schemas/graph.py
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from enum import Enum

class NodeType(str, Enum):
    FUNCTION = "function"
    CONDITION = "condition"
    LOOP = "loop"

class NodeDefinition(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    type: NodeType = Field(default=NodeType.FUNCTION, description="Type of node")
    tool: str = Field(..., description="Tool/function name from registry")
    config: dict[str, Any] = Field(default_factory=dict, description="Node configuration")

class EdgeDefinition(BaseModel):
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    condition: Optional[str] = Field(None, description="Optional condition for branching")

class GraphCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the workflow graph")
    description: Optional[str] = Field(None, description="Description of the workflow")
    nodes: List[NodeDefinition] = Field(..., description="List of nodes")
    edges: List[EdgeDefinition] = Field(..., description="List of edges")
    entry_node: str = Field(..., description="ID of the entry/start node")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Code Review Workflow",
                "description": "Automated code review agent",
                "nodes": [
                    {"id": "extract", "type": "function", "tool": "extract_functions"},
                    {"id": "complexity", "type": "function", "tool": "check_complexity"},
                ],
                "edges": [
                    {"source": "extract", "target": "complexity"}
                ],
                "entry_node": "extract"
            }
        }
    }

class GraphCreateResponse(BaseModel):
    graph_id: str
    message: str

class GraphRunRequest(BaseModel):
    graph_id: str = Field(..., description="ID of the graph to run")
    initial_state: dict[str, Any] = Field(default_factory=dict, description="Initial state for the workflow")

    model_config = {
        "json_schema_extra": {
            "example": {
                "graph_id": "abc123",
                "initial_state": {
                    "code": "def hello(): print('world')",
                    "quality_threshold": 7
                }
            }
        }
    }

class GraphRunResponse(BaseModel):
    run_id: str
    graph_id: str
    status: str
    message: str
    # added convenience URLs (frontend can use relative paths)
    poll_url: Optional[str] = None   # e.g. /graph/state/{run_id}
    ws_url: Optional[str] = None     # e.g. /ws/{run_id}
