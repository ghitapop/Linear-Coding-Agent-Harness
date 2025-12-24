"""Resume management for the Autonomous Orchestrator Framework."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from orchestrator.state_machine import (
    AgentSnapshot,
    PhaseStatus,
    PipelineState,
    PipelineStatus,
    StateMachine,
)


@dataclass
class ResumePoint:
    """Information about where to resume from."""

    phase: str
    context: dict[str, Any] = field(default_factory=dict)
    work_items_to_retry: list[str] = field(default_factory=list)
    is_crash_recovery: bool = False
    previous_error: Optional[str] = None

    def get_resume_prompt_context(self) -> str:
        """Generate context string for resume prompt.

        Returns:
            Context string to inject into agent prompt.
        """
        parts = []

        if self.is_crash_recovery:
            parts.append("NOTE: This is a crash recovery. The previous session ended unexpectedly.")

        if self.previous_error:
            parts.append(f"Previous error: {self.previous_error}")

        if self.work_items_to_retry:
            parts.append(f"Work items to retry: {', '.join(self.work_items_to_retry)}")

        if self.context.get("agent_summaries"):
            parts.append("Previous session context:")
            for summary in self.context["agent_summaries"]:
                parts.append(f"  - {summary}")

        return "\n".join(parts) if parts else ""


class ResumeManager:
    """Handles resuming from saved state."""

    # Heartbeat older than this is considered a crash
    CRASH_THRESHOLD = timedelta(minutes=5)

    def __init__(self, state_machine: StateMachine) -> None:
        """Initialize the resume manager.

        Args:
            state_machine: The state machine to resume from.
        """
        self._state_machine = state_machine

    def can_resume(self) -> bool:
        """Check if there's a state to resume from.

        Returns:
            True if resumable state exists.
        """
        state = self._state_machine.state
        return state.status in [
            PipelineStatus.RUNNING,
            PipelineStatus.PAUSED,
            PipelineStatus.STOPPING,
            PipelineStatus.STOPPED,
        ]

    def detect_crash(self) -> bool:
        """Detect if the previous run crashed.

        A crash is detected if:
        - The heartbeat is stale (older than CRASH_THRESHOLD)
        - The status is RUNNING but shutdown wasn't requested

        Returns:
            True if a crash is detected.
        """
        state = self._state_machine.state

        if not state.heartbeat:
            return False

        # Check if heartbeat is stale
        stale = datetime.utcnow() - state.heartbeat > self.CRASH_THRESHOLD

        # If running with stale heartbeat and no shutdown requested, it's a crash
        if state.status == PipelineStatus.RUNNING and stale and not state.shutdown_requested:
            return True

        return False

    def get_resume_point(self) -> ResumePoint:
        """Determine where to resume from.

        Returns:
            ResumePoint with phase and context information.
        """
        state = self._state_machine.state
        is_crash = self.detect_crash()

        # Find the phase to resume from
        resume_phase = self._find_resume_phase(state)

        # Build context from agent snapshots
        context = self._build_resume_context(state)

        # Get work items that need to be retried
        work_items_to_retry = list(state.interrupted_work_items)

        # Get previous error if any
        previous_error = None
        if resume_phase and resume_phase in state.phases:
            phase_state = state.phases[resume_phase]
            if phase_state.error:
                previous_error = phase_state.error

        return ResumePoint(
            phase=resume_phase or "initialize",
            context=context,
            work_items_to_retry=work_items_to_retry,
            is_crash_recovery=is_crash,
            previous_error=previous_error,
        )

    def _find_resume_phase(self, state: PipelineState) -> Optional[str]:
        """Find the phase to resume from.

        Args:
            state: Current pipeline state.

        Returns:
            Name of phase to resume from, or None if should start from beginning.
        """
        # If there's a current phase that was running, resume from there
        if state.current_phase:
            phase = state.phases.get(state.current_phase)
            if phase and phase.status in [PhaseStatus.RUNNING, PhaseStatus.FAILED]:
                return state.current_phase

        # Otherwise find the first non-completed phase
        from orchestrator.state_machine import DEFAULT_PHASES
        for phase_name in DEFAULT_PHASES:
            phase = state.phases.get(phase_name)
            if phase and phase.status in [PhaseStatus.PENDING, PhaseStatus.RUNNING, PhaseStatus.FAILED]:
                return phase_name

        return None

    def _build_resume_context(self, state: PipelineState) -> dict[str, Any]:
        """Build context from agent snapshots.

        Args:
            state: Current pipeline state.

        Returns:
            Context dictionary with agent summaries and other info.
        """
        context: dict[str, Any] = {}

        # Extract conversation summaries from agent snapshots
        if state.agent_snapshots:
            context["agent_summaries"] = [
                snapshot.conversation_summary
                for snapshot in state.agent_snapshots
                if snapshot.conversation_summary
            ]

            # Extract last tool calls for context
            context["last_tool_calls"] = [
                snapshot.last_tool_call
                for snapshot in state.agent_snapshots
                if snapshot.last_tool_call
            ]

        # Add phase output references
        context["phase_outputs"] = {
            name: phase.output_reference
            for name, phase in state.phases.items()
            if phase.output_reference
        }

        # Add last successful step
        if state.last_successful_step:
            context["last_successful_step"] = state.last_successful_step

        return context

    def prepare_for_resume(self) -> ResumePoint:
        """Prepare the state machine for resuming.

        This clears shutdown flags and prepares the state for a new run.

        Returns:
            ResumePoint with resume information.
        """
        resume_point = self.get_resume_point()

        # Clear shutdown flags
        self._state_machine.clear_shutdown_request()

        # Clear agent snapshots (they're now captured in ResumePoint)
        self._state_machine.clear_agent_snapshots()

        # Set status to running
        self._state_machine.set_status(PipelineStatus.RUNNING)

        # Update heartbeat
        self._state_machine.update_heartbeat()

        return resume_point

    def mark_work_items_for_retry(
        self,
        work_item_ids: list[str],
    ) -> None:
        """Mark work items for retry.

        This should be called after resuming to ensure interrupted
        work items are re-processed.

        Args:
            work_item_ids: List of work item IDs to retry.
        """
        for item_id in work_item_ids:
            self._state_machine.add_interrupted_work_item(item_id)

    def get_status_summary(self) -> dict[str, Any]:
        """Get a summary of the current state for display.

        Returns:
            Dictionary with status information.
        """
        state = self._state_machine.state

        # Count phase statuses
        phase_counts = {
            "completed": 0,
            "running": 0,
            "pending": 0,
            "failed": 0,
            "skipped": 0,
        }
        for phase in state.phases.values():
            status_key = phase.status.value
            phase_counts[status_key] = phase_counts.get(status_key, 0) + 1

        return {
            "project_id": state.project_id,
            "status": state.status.value,
            "current_phase": state.current_phase,
            "phases": phase_counts,
            "last_checkpoint": state.last_checkpoint.isoformat() if state.last_checkpoint else None,
            "shutdown_requested": state.shutdown_requested,
            "shutdown_reason": state.shutdown_reason,
            "interrupted_items": len(state.interrupted_work_items),
            "is_crash_recovery": self.detect_crash(),
        }
