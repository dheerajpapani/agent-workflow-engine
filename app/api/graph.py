# app/api/graph.py
import uuid
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Any

from app.schemas.graph import (
    GraphCreateRequest,
    GraphCreateResponse,
    GraphRunRequest,
    GraphRunResponse,
)
from app.schemas.state import StateResponse, WorkflowState, RunStatus
from app.engine.graph import WorkflowGraph
from app.engine.runner import run_workflow_async
from app.storage.memory import memory_storage
from app.utils.cache import cache
from app.api.websocket import broadcast_log
from app.workflows.code_review.workflow import CODE_REVIEW_WORKFLOW

router = APIRouter()


@router.post("/create", response_model=GraphCreateResponse)
async def create_graph(request: GraphCreateRequest) -> GraphCreateResponse:
    """
    Create a new workflow graph from JSON definition.
    Validate entry_node exists among nodes.
    """
    storage = memory_storage

    # Defensive: ensure entry_node exists in provided nodes
    node_ids = {n.id for n in request.nodes}
    if request.entry_node not in node_ids:
        raise HTTPException(status_code=400, detail=f"entry_node '{request.entry_node}' not found in nodes")

    graph_id = str(uuid.uuid4())[:8]

    graph = WorkflowGraph(
        graph_id=graph_id,
        name=request.name,
        description=request.description or "",
        nodes=request.nodes,
        edges=request.edges,
        entry_node=request.entry_node,
    )

    await storage.save_graph(graph_id, graph.to_dict())
    cache.set(f"graph:{graph_id}", graph, ttl=3600)

    return GraphCreateResponse(
        graph_id=graph_id,
        message=f"Graph '{request.name}' created successfully",
    )


@router.post("/create/code-review", response_model=GraphCreateResponse)
async def create_code_review_graph() -> GraphCreateResponse:
    """
    Convenience endpoint to create the pre-built Code Review workflow.
    """
    return await create_graph(CODE_REVIEW_WORKFLOW)


@router.post("/run", response_model=GraphRunResponse)
async def run_graph(
    request: GraphRunRequest,
    background_tasks: BackgroundTasks,
) -> GraphRunResponse:
    """
    Start a workflow execution with the given graph_id and initial state.
    Runs asynchronously in the background.
    Returns poll and websocket URLs for convenience.
    """
    storage = memory_storage

    # Load graph from cache or storage
    graph_obj = cache.get(f"graph:{request.graph_id}")
    if not graph_obj:
        graph_data = await storage.get_graph(request.graph_id)
        if not graph_data:
            raise HTTPException(status_code=404, detail="Graph not found")
        graph_obj = WorkflowGraph.from_dict(graph_data)
        cache.set(f"graph:{request.graph_id}", graph_obj, ttl=3600)

    run_id = str(uuid.uuid4())[:12]

    # Save initial run record
    await storage.save_run(run_id, {
        "run_id": run_id,
        "graph_id": request.graph_id,
        "status": RunStatus.PENDING.value,
        "initial_state": request.initial_state,
    })

    # Save initial workflow state
    initial_workflow_state = WorkflowState(
        run_id=run_id,
        graph_id=request.graph_id,
        status=RunStatus.PENDING,
        state_data=request.initial_state,
    )
    await storage.save_run_state(run_id, initial_workflow_state)

    # Start the async runner on the same event loop so broadcasting uses the same loop/manager
    try:
        asyncio.create_task(
            run_workflow_async(
                graph=graph_obj,
                initial_state=request.initial_state,
                run_id=run_id,
                storage=storage,
                broadcast_log=broadcast_log,
            )
        )
    except RuntimeError:
        # If no running loop (very unusual), fallback to BackgroundTasks
        background_tasks.add_task(
            run_workflow_async,
            graph=graph_obj,
            initial_state=request.initial_state,
            run_id=run_id,
            storage=storage,
            broadcast_log=broadcast_log,
        )

    # convenience URLs for frontend (relative)
    poll_url = f"/graph/state/{run_id}"
    ws_url = f"/ws/{run_id}"

    return GraphRunResponse(
        run_id=run_id,
        graph_id=request.graph_id,
        status="started",
        message="Workflow execution started in background",
        poll_url=poll_url,
        ws_url=ws_url,
    )


@router.get("/state/{run_id}", response_model=StateResponse)
async def get_state(run_id: str) -> StateResponse:
    storage = memory_storage

    state = await storage.get_run_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")

    return StateResponse(
        run_id=state.run_id,
        graph_id=state.graph_id,
        status=state.status.value,
        current_node=state.current_node,
        state_data=state.state_data,
        logs=state.logs,
        iteration_count=state.iteration_count,
        error=state.error,
    )


@router.get("/list")
async def list_graphs():
    storage = memory_storage
    graphs = await storage.list_graphs()
    return {"graphs": graphs, "count": len(graphs)}


@router.get("/{graph_id}")
async def get_graph(graph_id: str):
    storage = memory_storage
    graph_data = await storage.get_graph(graph_id)
    if not graph_data:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph_data


@router.delete("/{graph_id}")
async def delete_graph(graph_id: str):
    storage = memory_storage
    deleted = await storage.delete_graph(graph_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Graph not found")
    cache.delete(f"graph:{graph_id}")
    return {"message": "Graph deleted", "graph_id": graph_id}


@router.post("/pause/{run_id}")
async def pause_run(run_id: str):
    """
    Pause an ongoing run. Runner checks for PAUSED status and will suspend.
    """
    storage = memory_storage
    state = await storage.get_run_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")

    if state.status == RunStatus.COMPLETED or state.status == RunStatus.FAILED:
        raise HTTPException(status_code=400, detail="Cannot pause a completed/failed run")

    state.status = RunStatus.PAUSED
    await storage.save_run_state(run_id, state)
    return {"message": f"Run {run_id} paused"}


@router.post("/resume/{run_id}")
async def resume_run(run_id: str):
    """
    Resume a paused run.
    """
    storage = memory_storage
    state = await storage.get_run_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")

    if state.status != RunStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Run is not paused")

    state.status = RunStatus.RUNNING
    await storage.save_run_state(run_id, state)
    return {"message": f"Run {run_id} resumed"}
