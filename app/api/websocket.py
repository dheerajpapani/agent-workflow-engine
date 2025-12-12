# app/api/websocket.py
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class ConnectionManager:
    """Manage WebSocket connections keyed by run_id."""
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if run_id not in self._connections:
                self._connections[run_id] = set()
            self._connections[run_id].add(websocket)

    async def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if run_id in self._connections:
                self._connections[run_id].discard(websocket)
                if not self._connections[run_id]:
                    del self._connections[run_id]

    async def broadcast(self, run_id: str, message: str) -> None:
        """
        Broadcast a JSON message to all connected websockets for a run_id.
        If a connection fails, remove it from the set.
        """
        async with self._lock:
            if run_id not in self._connections:
                return
            dead = set()
            for ws in set(self._connections[run_id]):
                try:
                    await ws.send_json({"run_id": run_id, "type": "log", "message": message})
                except Exception as exc:
                    # defensive: mark dead connections for cleanup
                    try:
                        print(f"[websocket.broadcast] send error for run={run_id}: {exc}")
                    except Exception:
                        pass
                    dead.add(ws)
            for ws in dead:
                self._connections[run_id].discard(ws)

# single shared manager for the app
manager = ConnectionManager()

async def broadcast_log(run_id: str, message: str) -> None:
    """Helper to broadcast run logs. This is imported by the runner."""
    await manager.broadcast(run_id, message)

@router.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for run logs.
    Connect to /ws/{run_id} to receive messages: {"run_id":..., "type":"log", "message": "..."}
    """
    await manager.connect(run_id, websocket)
    try:
        await websocket.send_json({
            "run_id": run_id,
            "type": "connected",
            "message": f"Connected to log stream for run {run_id}",
        })
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_json({"run_id": run_id, "type": "pong", "message": "pong"})
            except asyncio.TimeoutError:
                # keep-alive ping for clients
                await websocket.send_json({"run_id": run_id, "type": "keepalive", "message": "keepalive"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(run_id, websocket)
