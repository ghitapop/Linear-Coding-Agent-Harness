"""Graceful shutdown handling for the Autonomous Orchestrator Framework."""

import asyncio
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

from orchestrator.state_machine import (
    AgentSnapshot,
    PipelineStatus,
    StateMachine,
)


@dataclass
class AgentHandle:
    """Handle to a running agent for shutdown coordination."""

    agent_id: str
    phase: str
    started_at: datetime
    current_work_item: Optional[str] = None
    last_tool_call: Optional[str] = None
    task: Optional[asyncio.Task[Any]] = None

    def to_snapshot(self, conversation_summary: str = "") -> AgentSnapshot:
        """Convert to an AgentSnapshot for persistence.

        Args:
            conversation_summary: Brief summary of agent conversation.

        Returns:
            AgentSnapshot for saving.
        """
        return AgentSnapshot(
            agent_id=self.agent_id,
            phase=self.phase,
            started_at=self.started_at,
            last_activity=datetime.utcnow(),
            current_work_item=self.current_work_item,
            last_tool_call=self.last_tool_call,
            conversation_summary=conversation_summary,
            can_resume=True,
        )


class GracefulShutdown:
    """Handles graceful shutdown with state preservation."""

    def __init__(
        self,
        state_machine: StateMachine,
        on_shutdown_start: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        on_shutdown_complete: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """Initialize the graceful shutdown handler.

        Args:
            state_machine: The state machine to save state to.
            on_shutdown_start: Optional callback when shutdown starts.
            on_shutdown_complete: Optional callback when shutdown completes.
        """
        self._state_machine = state_machine
        self._on_shutdown_start = on_shutdown_start
        self._on_shutdown_complete = on_shutdown_complete
        self._shutdown_requested = False
        self._running_agents: list[AgentHandle] = []
        self._shutdown_event = asyncio.Event()
        self._handlers_installed = False

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    def install_handlers(self) -> None:
        """Install signal handlers for graceful shutdown.

        Handles SIGINT (Ctrl+C), SIGTERM (kill), and SIGBREAK (Windows).
        """
        if self._handlers_installed:
            return

        # Get the current event loop or create one
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, will install when loop starts
            return

        # Unix signals
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                # Create a closure that captures the signal
                def make_handler(s: signal.Signals) -> Callable[[], None]:
                    def handler() -> None:
                        asyncio.create_task(self._handle_signal_async(s))
                    return handler

                loop.add_signal_handler(sig, make_handler(sig))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                signal.signal(sig, self._handle_signal_sync)

        # Windows SIGBREAK (Ctrl+Break)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self._handle_signal_sync)

        self._handlers_installed = True

    def _handle_signal_sync(self, signum: int, frame: Any) -> None:
        """Handle termination signal synchronously.

        Args:
            signum: Signal number.
            frame: Stack frame (unused).
        """
        print(f"\n[Shutdown] Signal {signum} received")
        self._shutdown_requested = True
        self._shutdown_event.set()

        # Schedule async shutdown if there's a running loop
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.shutdown(reason="signal"))
        except RuntimeError:
            # No running loop, just save state synchronously
            self._state_machine.request_shutdown("signal")

    async def _handle_signal_async(self, signum: signal.Signals) -> None:
        """Handle termination signal asynchronously.

        Args:
            signum: Signal number.
        """
        print(f"\n[Shutdown] Signal {signum.name} received")
        await self.shutdown(reason="signal")

    def register_agent(self, handle: AgentHandle) -> None:
        """Register a running agent for shutdown coordination.

        Args:
            handle: Handle to the running agent.
        """
        self._running_agents.append(handle)

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent that has completed.

        Args:
            agent_id: ID of the agent to unregister.
        """
        self._running_agents = [
            a for a in self._running_agents if a.agent_id != agent_id
        ]

    def update_agent(
        self,
        agent_id: str,
        current_work_item: Optional[str] = None,
        last_tool_call: Optional[str] = None,
    ) -> None:
        """Update agent state for snapshot.

        Args:
            agent_id: ID of the agent to update.
            current_work_item: Current work item being processed.
            last_tool_call: Last tool call made.
        """
        for agent in self._running_agents:
            if agent.agent_id == agent_id:
                if current_work_item is not None:
                    agent.current_work_item = current_work_item
                if last_tool_call is not None:
                    agent.last_tool_call = last_tool_call
                break

    async def shutdown(
        self,
        reason: str = "user_request",
        timeout: int = 30,
    ) -> None:
        """Perform graceful shutdown with state preservation.

        Args:
            reason: Reason for shutdown.
            timeout: Maximum seconds to wait for agents to stop.
        """
        if self._shutdown_requested and self._state_machine.state.status == PipelineStatus.STOPPED:
            return  # Already shut down

        self._shutdown_requested = True
        self._shutdown_event.set()

        print("[Shutdown] Saving state and stopping gracefully...")

        # 1. Call shutdown start callback
        if self._on_shutdown_start:
            await self._on_shutdown_start()

        # 2. Set stopping status
        self._state_machine.set_status(PipelineStatus.STOPPING)

        # 3. Wait for agents to reach safe point
        print(f"[Shutdown] Waiting for {len(self._running_agents)} agent(s) to reach safe point...")
        try:
            await asyncio.wait_for(
                self._wait_for_agents_safe_point(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            print(f"[Shutdown] Timeout waiting for agents, forcing save")

        # 4. Capture agent snapshots
        snapshots = self._capture_agent_snapshots()
        print(f"[Shutdown] Captured {len(snapshots)} agent snapshot(s)")

        # 5. Collect interrupted work items
        interrupted_items = self._collect_interrupted_items()

        # 6. Save state atomically
        await self._save_state_atomic(
            reason=reason,
            snapshots=snapshots,
            interrupted_items=interrupted_items,
        )

        # 7. Set stopped status
        self._state_machine.set_status(PipelineStatus.STOPPED)

        # 8. Call shutdown complete callback
        if self._on_shutdown_complete:
            await self._on_shutdown_complete()

        print("[Shutdown] State saved successfully. Safe to exit.")
        print(f"  To resume: python main.py --resume")

    async def _wait_for_agents_safe_point(self) -> None:
        """Wait for all agents to reach a safe stopping point."""
        tasks_to_cancel = []
        for agent in self._running_agents:
            if agent.task and not agent.task.done():
                tasks_to_cancel.append(agent.task)

        if tasks_to_cancel:
            # Give agents a chance to finish their current operation
            done, pending = await asyncio.wait(
                tasks_to_cancel,
                timeout=5.0,
                return_when=asyncio.ALL_COMPLETED,
            )

            # Cancel any still pending
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _capture_agent_snapshots(self) -> list[AgentSnapshot]:
        """Capture snapshots of all running agents.

        Returns:
            List of agent snapshots.
        """
        snapshots = []
        for agent in self._running_agents:
            snapshot = agent.to_snapshot()
            snapshots.append(snapshot)
        return snapshots

    def _collect_interrupted_items(self) -> list[str]:
        """Collect IDs of work items that were interrupted.

        Returns:
            List of interrupted work item IDs.
        """
        items = []
        for agent in self._running_agents:
            if agent.current_work_item:
                items.append(agent.current_work_item)
        return items

    async def _save_state_atomic(
        self,
        reason: str,
        snapshots: list[AgentSnapshot],
        interrupted_items: list[str],
    ) -> None:
        """Save state atomically.

        Args:
            reason: Shutdown reason.
            snapshots: Agent snapshots to save.
            interrupted_items: List of interrupted work item IDs.
        """
        state = self._state_machine.state

        # Update state with shutdown info
        state.shutdown_requested = True
        state.shutdown_reason = reason
        state.agent_snapshots = snapshots
        state.interrupted_work_items = interrupted_items
        state.last_checkpoint = datetime.utcnow()

        # Save atomically (handled by state machine)
        self._state_machine.save()

    def check_should_stop(self) -> bool:
        """Check if shutdown was requested. Call this in loops.

        Returns:
            True if shutdown has been requested.
        """
        return self._shutdown_requested

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to be requested.

        This can be used to block until shutdown is signaled.
        """
        await self._shutdown_event.wait()


def create_shutdown_handler(
    state_machine: StateMachine,
) -> GracefulShutdown:
    """Create and configure a shutdown handler.

    Args:
        state_machine: The state machine for this project.

    Returns:
        Configured GracefulShutdown handler.
    """
    handler = GracefulShutdown(state_machine)

    # Install handlers if we're on the main thread
    if sys.platform != "win32":
        # On Unix, we can install handlers immediately
        try:
            handler.install_handlers()
        except RuntimeError:
            pass  # No event loop yet, will install later

    return handler
