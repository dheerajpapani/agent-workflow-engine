# app/engine/graph.py
from typing import Any, Optional
from app.schemas.graph import NodeDefinition, EdgeDefinition

class WorkflowGraph:
    """
    Workflow Graph representation.
    """
    def __init__(
        self,
        graph_id: str,
        name: str,
        nodes: list[NodeDefinition],
        edges: list[EdgeDefinition],
        entry_node: str,
        description: str = ""
    ):
        self.graph_id = graph_id
        self.name = name
        self.description = description
        self.entry_node = entry_node

        self._nodes = {n.id: n for n in nodes}
        self._edges = {}
        for edge in edges:
            self._edges.setdefault(edge.source, []).append(edge)

    def get_node(self, node_id: str) -> Optional[NodeDefinition]:
        return self._nodes.get(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[EdgeDefinition]:
        return self._edges.get(node_id, [])

    def get_next_node(self, current_node_id: str, state: dict[str, Any]) -> Optional[str]:
        edges = self.get_outgoing_edges(current_node_id)
        if not edges:
            return None
        if len(edges) == 1 and not edges[0].condition:
            return edges[0].target
        default_target = None
        for edge in edges:
            if edge.condition:
                if self._evaluate_condition(edge.condition, state):
                    return edge.target
            else:
                default_target = edge.target
        return default_target

    def _evaluate_condition(self, condition: str, state: dict[str, Any]) -> bool:
        try:
            safe_context = {"state": state, **state}
            return bool(eval(condition, {"__builtins__": {}}, safe_context))
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "entry_node": self.entry_node,
            "nodes": [n.model_dump() for n in self._nodes.values()],
            "edges": [e.model_dump() for edges in self._edges.values() for e in edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowGraph":
        return cls(
            graph_id=data["graph_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=[NodeDefinition(**n) for n in data.get("nodes", [])],
            edges=[EdgeDefinition(**e) for e in data.get("edges", [])],
            entry_node=data.get("entry_node", ""),
        )
