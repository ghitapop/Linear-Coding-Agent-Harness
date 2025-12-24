"""REST API adapter for Docker deployment mode."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID

from adapters.base import InputAdapter
from orchestrator.state_machine import PipelineState


@dataclass
class PendingApproval:
    """Represents a pending approval request."""

    project_id: UUID
    phase: str
    summary: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved: Optional[bool] = None
    comment: Optional[str] = None


@dataclass
class PendingClarification:
    """Represents a pending clarification request."""

    project_id: UUID
    question: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    response: Optional[str] = None


class APIAdapter(InputAdapter):
    """REST API adapter for non-interactive Docker deployment.

    This adapter is used when the orchestrator runs in Docker/API mode.
    Instead of interactive prompts, it:
    - Stores pending requests (approvals, clarifications)
    - Waits for responses via API endpoints
    - Can be configured for auto-approval in full autonomy mode
    """

    def __init__(
        self,
        project_id: Optional[UUID] = None,
        auto_approve: bool = False,
        approval_timeout: int = 3600,  # 1 hour default
        on_status_change: Optional[Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """Initialize the API adapter.

        Args:
            project_id: Current project ID.
            auto_approve: If True, automatically approve all checkpoints.
            approval_timeout: Seconds to wait for approval before timing out.
            on_status_change: Optional callback for status changes (for WebSocket notifications).
        """
        self._project_id = project_id
        self._auto_approve = auto_approve
        self._approval_timeout = approval_timeout
        self._on_status_change = on_status_change

        # Pending requests storage
        self._pending_approvals: dict[UUID, PendingApproval] = {}
        self._pending_clarifications: dict[UUID, PendingClarification] = {}

        # Events for async waiting
        self._approval_events: dict[UUID, asyncio.Event] = {}
        self._clarification_events: dict[UUID, asyncio.Event] = {}

        # Message queue for show_message calls
        self._messages: list[dict[str, Any]] = []

        # Running state
        self._running = False

    @property
    def project_id(self) -> Optional[UUID]:
        """Get current project ID."""
        return self._project_id

    @project_id.setter
    def project_id(self, value: UUID) -> None:
        """Set current project ID."""
        self._project_id = value

    async def start(self) -> None:
        """Start the API adapter."""
        self._running = True
        await self._notify_status("started", {"message": "Orchestrator started"})

    async def stop(self) -> None:
        """Stop the API adapter."""
        self._running = False
        # Cancel any pending waits
        for event in self._approval_events.values():
            event.set()
        for event in self._clarification_events.values():
            event.set()
        await self._notify_status("stopped", {"message": "Orchestrator stopped"})

    async def get_initial_idea(self) -> str:
        """Get initial idea - in API mode, this comes from the POST request.

        Returns:
            Empty string (idea should be provided via API).
        """
        # In API mode, the idea is provided when creating the project
        # This method should not be called directly
        return ""

    async def get_project_name(self, suggested_name: Optional[str] = None) -> str:
        """Get project name - in API mode, this comes from the POST request.

        Args:
            suggested_name: Suggested name.

        Returns:
            The suggested name or a default.
        """
        return suggested_name or "project"

    async def get_approval(
        self,
        summary: str,
        phase: str,
        options: Optional[list[str]] = None,
    ) -> bool:
        """Get user approval at checkpoints.

        In API mode, this either auto-approves or waits for approval via API.

        Args:
            summary: Summary of what to approve.
            phase: Current phase name.
            options: Optional list of options.

        Returns:
            True if approved, False otherwise.
        """
        if self._auto_approve:
            await self._notify_status("auto_approved", {
                "phase": phase,
                "summary": summary,
            })
            return True

        if not self._project_id:
            return False

        # Create pending approval
        approval = PendingApproval(
            project_id=self._project_id,
            phase=phase,
            summary=summary,
        )
        self._pending_approvals[self._project_id] = approval

        # Create event for waiting
        event = asyncio.Event()
        self._approval_events[self._project_id] = event

        # Notify about pending approval
        await self._notify_status("approval_pending", {
            "project_id": str(self._project_id),
            "phase": phase,
            "summary": summary,
        })

        # Wait for approval with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=self._approval_timeout)
        except asyncio.TimeoutError:
            # Timeout - treat as rejection
            self._pending_approvals.pop(self._project_id, None)
            self._approval_events.pop(self._project_id, None)
            await self._notify_status("approval_timeout", {
                "project_id": str(self._project_id),
                "phase": phase,
            })
            return False

        # Get result
        approval = self._pending_approvals.pop(self._project_id, None)
        self._approval_events.pop(self._project_id, None)

        if approval and approval.approved is not None:
            return approval.approved

        return False

    async def get_clarification(self, question: str) -> str:
        """Ask user for clarification.

        In API mode, this waits for response via API.

        Args:
            question: The question to ask.

        Returns:
            The user's response or empty string on timeout.
        """
        if not self._project_id:
            return ""

        # Create pending clarification
        clarification = PendingClarification(
            project_id=self._project_id,
            question=question,
        )
        self._pending_clarifications[self._project_id] = clarification

        # Create event for waiting
        event = asyncio.Event()
        self._clarification_events[self._project_id] = event

        # Notify about pending clarification
        await self._notify_status("clarification_pending", {
            "project_id": str(self._project_id),
            "question": question,
        })

        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=self._approval_timeout)
        except asyncio.TimeoutError:
            self._pending_clarifications.pop(self._project_id, None)
            self._clarification_events.pop(self._project_id, None)
            return ""

        # Get result
        clarification = self._pending_clarifications.pop(self._project_id, None)
        self._clarification_events.pop(self._project_id, None)

        if clarification and clarification.response is not None:
            return clarification.response

        return ""

    async def show_progress(self, state: PipelineState) -> None:
        """Display current progress.

        In API mode, this notifies via callback/WebSocket.

        Args:
            state: Current pipeline state.
        """
        await self._notify_status("progress", {
            "project_id": state.project_id,
            "status": state.status.value,
            "current_phase": state.current_phase,
            "phases": {
                name: {
                    "status": phase.status.value,
                    "retry_count": phase.retry_count,
                }
                for name, phase in state.phases.items()
            },
        })

    async def show_message(
        self,
        message: str,
        level: str = "info",
    ) -> None:
        """Show a message.

        In API mode, messages are queued and can be retrieved via API.

        Args:
            message: The message to display.
            level: Message level (info, warning, error, success).
        """
        msg = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "project_id": str(self._project_id) if self._project_id else None,
        }
        self._messages.append(msg)

        # Keep only last 1000 messages
        if len(self._messages) > 1000:
            self._messages = self._messages[-1000:]

        await self._notify_status("message", msg)

    async def show_error(
        self,
        error: str,
        options: Optional[list[str]] = None,
    ) -> str:
        """Show error and get user decision.

        In API mode, this logs the error and returns the first option.

        Args:
            error: The error message.
            options: Optional list of options.

        Returns:
            The first option (auto-select).
        """
        await self.show_message(error, level="error")
        options = options or ["retry"]
        return options[0]

    async def get_command(self) -> tuple[str, list[str]]:
        """Get the next command.

        In API mode, commands come via REST endpoints, not this method.

        Returns:
            Empty command tuple.
        """
        # In API mode, commands are handled by FastAPI routes
        # This shouldn't be called
        return ("", [])

    async def handle_command(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> Optional[str]:
        """Handle a command.

        In API mode, commands are handled by FastAPI routes.

        Args:
            command: The command name.
            args: Command arguments.
            context: Context dict.

        Returns:
            None (commands handled elsewhere).
        """
        return None

    # API-specific methods for external callers

    def submit_approval(
        self,
        project_id: UUID,
        approved: bool,
        comment: Optional[str] = None,
    ) -> bool:
        """Submit an approval response.

        Called by the API endpoint when user approves/rejects.

        Args:
            project_id: Project ID.
            approved: Whether approved.
            comment: Optional comment.

        Returns:
            True if there was a pending approval to respond to.
        """
        if project_id not in self._pending_approvals:
            return False

        approval = self._pending_approvals[project_id]
        approval.approved = approved
        approval.comment = comment

        # Signal the waiting coroutine
        if project_id in self._approval_events:
            self._approval_events[project_id].set()

        return True

    def submit_clarification(
        self,
        project_id: UUID,
        response: str,
    ) -> bool:
        """Submit a clarification response.

        Called by the API endpoint when user responds to a question.

        Args:
            project_id: Project ID.
            response: User's response.

        Returns:
            True if there was a pending clarification to respond to.
        """
        if project_id not in self._pending_clarifications:
            return False

        clarification = self._pending_clarifications[project_id]
        clarification.response = response

        # Signal the waiting coroutine
        if project_id in self._clarification_events:
            self._clarification_events[project_id].set()

        return True

    def get_pending_approval(self, project_id: UUID) -> Optional[dict[str, Any]]:
        """Get pending approval for a project.

        Args:
            project_id: Project ID.

        Returns:
            Pending approval info or None.
        """
        approval = self._pending_approvals.get(project_id)
        if approval:
            return {
                "project_id": str(approval.project_id),
                "phase": approval.phase,
                "summary": approval.summary,
                "created_at": approval.created_at.isoformat(),
            }
        return None

    def get_pending_clarification(self, project_id: UUID) -> Optional[dict[str, Any]]:
        """Get pending clarification for a project.

        Args:
            project_id: Project ID.

        Returns:
            Pending clarification info or None.
        """
        clarification = self._pending_clarifications.get(project_id)
        if clarification:
            return {
                "project_id": str(clarification.project_id),
                "question": clarification.question,
                "created_at": clarification.created_at.isoformat(),
            }
        return None

    def get_messages(
        self,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get recent messages.

        Args:
            limit: Maximum number of messages.
            level: Optional filter by level.

        Returns:
            List of messages.
        """
        messages = self._messages
        if level:
            messages = [m for m in messages if m["level"] == level]
        return messages[-limit:]

    async def _notify_status(self, event: str, data: dict[str, Any]) -> None:
        """Notify about status change.

        Args:
            event: Event name.
            data: Event data.
        """
        if self._on_status_change:
            try:
                await self._on_status_change(event, data)
            except Exception:
                pass  # Don't let callback errors break the adapter


def create_api_adapter(
    project_id: Optional[UUID] = None,
    auto_approve: bool = False,
) -> APIAdapter:
    """Create an API adapter instance.

    Args:
        project_id: Optional initial project ID.
        auto_approve: If True, automatically approve all checkpoints.

    Returns:
        Configured APIAdapter.
    """
    return APIAdapter(
        project_id=project_id,
        auto_approve=auto_approve,
    )
