import asyncio
from app.workflows.code_review.workflow import CODE_REVIEW_WORKFLOW
from app.engine.graph import WorkflowGraph
from app.engine.runner import run_workflow_async
from app.storage.memory import memory_storage
from app.api.websocket import broadcast_log  # must point to same manager

async def main():
    graph_req = CODE_REVIEW_WORKFLOW
    graph = WorkflowGraph(
        graph_id="dbg-graph",
        name=graph_req.name,
        description=graph_req.description or "",
        nodes=graph_req.nodes,
        edges=graph_req.edges,
        entry_node=graph_req.entry_node,
    )
    run_id="dbg-run"
    initial_state={"code":"def foo():\n  return 1"}
    await memory_storage.save_graph("dbg-graph", graph.to_dict())
    await memory_storage.save_run(run_id, {"run_id":run_id,"graph_id":"dbg-graph","status":"pending"})
    from app.schemas.state import WorkflowState
    ws = WorkflowState(run_id=run_id, graph_id="dbg-graph", state_data=initial_state)
    await memory_storage.save_run_state(run_id, ws)
    # run directly
    await run_workflow_async(graph, initial_state, run_id, memory_storage, broadcast_log=broadcast_log)

if __name__ == "__main__":
    asyncio.run(main())
