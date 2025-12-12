# app/engine/registry.py
from typing import Callable, Any, Dict, List
from functools import wraps
from fastapi import WebSocket

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def register(self, name: str = None, description: str = "") -> Callable:
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            @wraps(func)
            def wrapper(state: dict[str, Any]):
                return func(state)
            self._tools[tool_name] = wrapper
            self._metadata[tool_name] = {
                "name": tool_name,
                "description": description or (func.__doc__ or ""),
                "function": func.__name__,
            }
            return wrapper
        return decorator

    def register_function(self, func: Callable, name: str = None, description: str = "") -> None:
        tool_name = name or func.__name__
        self._tools[tool_name] = func
        self._metadata[tool_name] = {
            "name": tool_name,
            "description": description or (func.__doc__ or ""),
            "function": func.__name__,
        }

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def exists(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_metadata(self, name: str) -> dict[str, Any]:
        return self._metadata.get(name, {})

# Global instance
tool_registry = ToolRegistry()


class WebSocketConnectionManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        await websocket.accept()
        self.connections.setdefault(run_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str):
        if run_id in self.connections:
            self.connections[run_id] = [
                ws for ws in self.connections[run_id] if ws != websocket
            ]

    async def broadcast(self, run_id: str, message: str):
        if run_id not in self.connections:
            return
        dead = []
        for ws in self.connections[run_id]:
            try:
                await ws.send_json({"type": "log", "message": message})
            except:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws, run_id)


connection_manager = WebSocketConnectionManager()