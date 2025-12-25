"""Heartbeat management for crash detection in the Autonomous Orchestrator Framework."""

import asyncio
from typing import Optional

from server.harness_agent.orchestrator.state_machine import StateMachine


class HeartbeatManager:
    """Manages periodic heartbeat updates for crash detection.

    The heartbeat is updated every interval to indicate the orchestrator
    is still running. If the heartbeat becomes stale, it indicates a crash.
    """

    DEFAULT_INTERVAL = 60  # seconds

    def __init__(
        self,
        state_machine: StateMachine,
        interval: int = DEFAULT_INTERVAL,
    ) -> None:
        """Initialize the heartbeat manager.

        Args:
            state_machine: The state machine to update.
            interval: Heartbeat interval in seconds.
        """
        self._state_machine = state_machine
        self._interval = interval
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if heartbeat is running."""
        return self._running

    def start(self) -> None:
        """Start the heartbeat background task.

        The heartbeat will update every interval seconds until stopped.
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop the heartbeat background task."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _heartbeat_loop(self) -> None:
        """Background loop that updates heartbeat periodically."""
        while self._running:
            try:
                self._state_machine.update_heartbeat()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue heartbeat
                await asyncio.sleep(self._interval)

    def update_now(self) -> None:
        """Update heartbeat immediately.

        This can be called manually at critical points like:
        - After completing a tool call
        - After completing a work item
        - Before starting a long operation
        """
        self._state_machine.update_heartbeat()

    async def __aenter__(self) -> "HeartbeatManager":
        """Context manager entry - start heartbeat."""
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> None:
        """Context manager exit - stop heartbeat."""
        await self.stop()


def create_heartbeat_manager(
    state_machine: StateMachine,
    interval: int = HeartbeatManager.DEFAULT_INTERVAL,
) -> HeartbeatManager:
    """Create a heartbeat manager.

    Args:
        state_machine: The state machine for this project.
        interval: Heartbeat interval in seconds.

    Returns:
        Configured HeartbeatManager.
    """
    return HeartbeatManager(state_machine, interval)
