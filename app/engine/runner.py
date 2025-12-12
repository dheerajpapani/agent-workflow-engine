# app/engine/runner.py
"""
Workflow Runner - executes workflow graphs asynchronously.

Responsibilities:
- Execute nodes in order, handle branching/looping.
- Support pause/resume via state.status == RunStatus.PAUSED.
- Emit logs via `on_log` callback.
- Ensure status changes are logged & persisted by calling `on_log`.
- Support sync and async tool functions from the tool registry.
"""

import asyncio
from typing import Any, Optional, Callable
from datetime import datetime

from app.engine.graph import WorkflowGraph
from app.engine.state import StateManager
from app.engine.registry import tool_registry  # global registry instance
from app.schemas.state import WorkflowState, RunStatus


class WorkflowRunner:
    """
    Executes a WorkflowGraph, updating a StateManager and invoking an on_log callback
    for each log entry or important state change.
    """

    def __init__(
        self,
        graph: WorkflowGraph,
        state_manager: StateManager,
        registry: Any = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self.graph = graph
        self.state_manager = state_manager
        self.registry = registry or tool_registry
        # on_log: function that accepts a single string message. It's responsible for
        # broadcasting and/or persisting state externally (provided by caller).
        self.on_log = on_log or (lambda message: None)

    # --- Helpers for logging and status updates --------------------------------
    def _log(self, message: str) -> None:
        """
        Add a log entry to the state and call the external on_log callback.
        The on_log callback should itself be non-blocking (or create tasks).
        """
        timestamped = f"[{datetime.utcnow().isoformat()}] {message}"
        self.state_manager.add_log(timestamped)
        try:
            # Keep callback small and non-blocking in implementation provided by run_workflow_async
            self.on_log(timestamped)
        except Exception:
            # Never fail the runner due to logging problems
            pass

    def _set_status(self, status: RunStatus, message: Optional[str] = None) -> None:
        """
        Set workflow status and emit a log entry describing the status change.
        """
        self.state_manager.set_status(status)
        msg = message or f"Status changed -> {status.value}"
        self._log(msg)

    # --- Node execution -------------------------------------------------------
    async def _execute_node(self, node) -> None:
        """
        Execute a single node's tool function and update state with returned dict.
        Raises on error to be caught by outer run loop.
        """
        try:
            if not self.registry.exists(node.tool):
                raise ValueError(f"Tool '{node.tool}' not found in registry")

            tool_func = self.registry.get(node.tool)
            current_state = self.state_manager.get_data()
            # Provide node config to tool via reserved key (tool should remove it if returned)
            current_state["_node_config"] = node.config

            # Support both sync and async tool functions
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(current_state)
            else:
                # Run sync tool in threadpool to avoid blocking event loop if it's CPU-bound
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, tool_func, current_state)

            if isinstance(result, dict):
                # Prevent accidental leaking of internal config into persisted state
                result.pop("_node_config", None)
                self.state_manager.update_data(result)

            self._log(f"Node '{node.id}' completed")
        except Exception as exc:
            # Log error and re-raise to be handled by run()
            self._log(f"Error in node '{node.id}': {str(exc)}")
            raise

    # --- Main execution loop -------------------------------------------------
    async def run(self) -> dict[str, Any]:
        """
        Execute the workflow from the graph's entry node until completion or failure.

        Returns:
            A dict representation of the final state (StateManager.to_response()).
        """
        # If starting fresh, flip to RUNNING (if not resuming from PAUSED)
        if self.state_manager.state.status != RunStatus.PAUSED:
            self._set_status(RunStatus.RUNNING, message="Workflow starting (set RUNNING)")

        current_node_id = self.graph.entry_node

        self._log(f"Starting workflow '{self.graph.name}'")
        self._log(f"Entry node: {current_node_id}")

        try:
            while current_node_id:
                # Honor PAUSED status (cooperative pause)
                if self.state_manager.state.status == RunStatus.PAUSED:
                    self._log("Workflow paused; waiting to resume...")
                    while self.state_manager.state.status == RunStatus.PAUSED:
                        await asyncio.sleep(0.5)
                    self._log("Workflow resumed; continuing execution")
                    # If resume sets RUNNING elsewhere, continue

                # Prevent infinite loops via iteration counter
                if not self.state_manager.increment_iteration():
                    self._set_status(RunStatus.FAILED, message="Max iterations reached - failing run")
                    break

                node = self.graph.get_node(current_node_id)
                if not node:
                    self.state_manager.set_error(f"Node '{current_node_id}' not found")
                    break

                # Mark the current node in state and execute
                self.state_manager.set_current_node(current_node_id)
                self._log(f"Executing node: {node.id} (tool: {node.tool})")

                # Execute node (may raise)
                await self._execute_node(node)

                # Determine next node based on graph branching/conditions
                current_node_id = self.graph.get_next_node(current_node_id, self.state_manager.get_data())

                # small yield to event loop
                await asyncio.sleep(0.01)

            # If we exit the loop naturally and status still RUNNING -> COMPLETED
            if self.state_manager.state.status == RunStatus.RUNNING:
                self._set_status(RunStatus.COMPLETED, message="Workflow completed successfully")

        except Exception as e:
            # Ensure failure is recorded
            self.state_manager.set_error(str(e))
            self._log(f"Workflow failed: {str(e)}")

        # Return final API-friendly response
        return self.state_manager.to_response()


# --- Runner wrapper for background tasks -------------------------------------
async def run_workflow_async(
    graph: WorkflowGraph,
    initial_state: dict[str, Any],
    run_id: str,
    storage,
    broadcast_log: Optional[Callable[[str, str], Any]] = None,
) -> dict[str, Any]:
    """
    Wrapper that creates a WorkflowState -> StateManager, wires up an on_log callback
    which both broadcasts logs (if broadcast_log provided) and persists state to storage,
    then runs the WorkflowRunner and ensures final state is saved.

    Args:
        graph: WorkflowGraph instance to execute.
        initial_state: dictionary initial state for the workflow.
        run_id: unique run identifier (used for persistence and broadcasting).
        storage: storage adapter (must implement save_run_state).
        broadcast_log: optional callable (run_id, message) -> awaitable to broadcast logs (e.g. WebSocket).
    Returns:
        dict: final workflow response (from StateManager.to_response()).
    """

    # Initialize workflow state (PENDING initially)
    workflow_state = WorkflowState(
        run_id=run_id,
        graph_id=graph.graph_id,
        state_data=initial_state or {},
        status=RunStatus.PENDING,
    )

    state_manager = StateManager(workflow_state)

    # Persist helper (async)
    async def persist_state():
        try:
            await storage.save_run_state(run_id, state_manager.state)
        except Exception:
            # best-effort persistence; do not raise to avoid stopping runner
            pass

    # Immediately flip to RUNNING and persist so UI sees the new status early
    state_manager.set_status(RunStatus.RUNNING)
    try:
        # await persistence so the state is visible quickly to clients
        await persist_state()
    except Exception:
        pass

    # on_log callback invoked by WorkflowRunner._log (synchronous). Keep it minimal: schedule async tasks.
    def on_log(message: str):
        # debug print to server stdout for visibility
        try:
            print(f"[runner:on_log] run_id={run_id} message={message}")
        except Exception:
            pass

        # broadcast via provided callable (if any)
        if broadcast_log:
            try:
                # broadcast_log expected signature: awaitable broadcast_log(run_id, message)
                asyncio.create_task(broadcast_log(run_id, message))
            except Exception as exc:
                try:
                    print(f"[runner:on_log] broadcast scheduling error: {exc}")
                except Exception:
                    pass

        # schedule persistence task (fire-and-forget)
        try:
            asyncio.create_task(persist_state())
        except Exception as exc:
            try:
                print(f"[runner:on_log] persist scheduling error: {exc}")
            except Exception:
                pass

    runner = WorkflowRunner(
        graph=graph,
        state_manager=state_manager,
        on_log=on_log,
    )

    # Run the workflow (this will call on_log which persists state as logs are added)
    result = await runner.run()

    # Final persist to ensure fully up-to-date state is saved
    try:
        await storage.save_run_state(run_id, state_manager.state)
    except Exception:
        pass

    return result
