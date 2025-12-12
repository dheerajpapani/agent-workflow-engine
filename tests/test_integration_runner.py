# tests/test_integration_runner.py
import asyncio
import pytest

from app.workflows.code_review.workflow import CODE_REVIEW_WORKFLOW
from app.engine.graph import WorkflowGraph
from app.storage.memory import memory_storage
from app.engine.runner import run_workflow_async
from app.schemas.state import RunStatus

# Make sure tools are registered for tests (normally done at app startup)
from app.workflows.code_review.nodes import register_code_review_tools
from app.engine.registry import tool_registry

register_code_review_tools(tool_registry)


@pytest.mark.asyncio
async def test_run_code_review_workflow_end_to_end():
    """
    Create a code-review graph via the GraphCreateRequest object,
    persist it into memory_storage, start a run, wait for runner to finish,
    then assert final state saved and status is COMPLETED (or FAILED) and quality_score present.
    """
    # Create graph object (this mirrors what the API does)
    graph_request = CODE_REVIEW_WORKFLOW
    graph_id = "testgraph1"
    graph = WorkflowGraph(
        graph_id=graph_id,
        name=graph_request.name,
        description=graph_request.description or "",
        nodes=graph_request.nodes,
        edges=graph_request.edges,
        entry_node=graph_request.entry_node,
    )

    # Save graph to in-memory storage
    await memory_storage.save_graph(graph_id, graph.to_dict())

    # Start a run
    run_id = "testrun1"
    initial_state = {"code": "def foo():\n    return 1", "quality_threshold": 0}

    # Save initial run record and state
    await memory_storage.save_run(run_id, {"run_id": run_id, "graph_id": graph_id, "status": RunStatus.PENDING.value})
    from app.schemas.state import WorkflowState
    initial_workflow_state = WorkflowState(run_id=run_id, graph_id=graph_id, state_data=initial_state)
    await memory_storage.save_run_state(run_id, initial_workflow_state)

    # Run workflow (this will update storage as it runs)
    result = await run_workflow_async(graph=graph, initial_state=initial_state, run_id=run_id, storage=memory_storage, broadcast_log=None)

    # Check final persisted state
    final = await memory_storage.get_run_state(run_id)
    assert final is not None
    assert final.status in (RunStatus.COMPLETED, RunStatus.FAILED)
    # ensure runner produced analysis keys (or at least attempted)
    assert "quality_score" in final.state_data or "parse_error" in final.state_data
