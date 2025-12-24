"""Base adapter interface for the Autonomous Orchestrator Framework."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from orchestrator.state_machine import PipelineState


class InputAdapter(ABC):
    """Abstract interface for user interaction.

    This interface defines how the orchestrator receives input and
    communicates with users. Implementations can be:
    - CLI (interactive command line)
    - REST API (HTTP endpoints)
    - WebSocket (real-time)
    - Other integrations (Slack, Discord, etc.)
    """

    @abstractmethod
    async def get_initial_idea(self) -> str:
        """Get the initial project idea from user.

        This is called when starting a new project.

        Returns:
            The project idea/description from the user.
        """
        pass

    @abstractmethod
    async def get_project_name(self, suggested_name: Optional[str] = None) -> str:
        """Get the project name from user.

        Args:
            suggested_name: Optional suggested name based on the idea.

        Returns:
            The chosen project name.
        """
        pass

    @abstractmethod
    async def get_approval(
        self,
        summary: str,
        phase: str,
        options: Optional[list[str]] = None,
    ) -> bool:
        """Get user approval at checkpoints.

        Args:
            summary: Summary of what to approve.
            phase: Current phase name.
            options: Optional list of options (e.g., ["Yes", "No", "View"]).

        Returns:
            True if approved, False otherwise.
        """
        pass

    @abstractmethod
    async def get_clarification(self, question: str) -> str:
        """Ask user for clarification during phases.

        Args:
            question: The question to ask.

        Returns:
            The user's response.
        """
        pass

    @abstractmethod
    async def show_progress(self, state: PipelineState) -> None:
        """Display current progress to user.

        Args:
            state: Current pipeline state.
        """
        pass

    @abstractmethod
    async def show_message(
        self,
        message: str,
        level: str = "info",
    ) -> None:
        """Show a message to the user.

        Args:
            message: The message to display.
            level: Message level (info, warning, error, success).
        """
        pass

    @abstractmethod
    async def show_error(
        self,
        error: str,
        options: Optional[list[str]] = None,
    ) -> str:
        """Show error and get user decision.

        Args:
            error: The error message.
            options: Optional list of options (e.g., ["Retry", "Skip", "Abort"]).

        Returns:
            The chosen option.
        """
        pass

    @abstractmethod
    async def get_command(self) -> tuple[str, list[str]]:
        """Get the next command from user.

        Returns:
            Tuple of (command_name, arguments).
            command_name is empty string for regular input.
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the adapter.

        Called when the orchestrator starts.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter.

        Called when the orchestrator stops.
        """
        pass

    async def handle_command(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> Optional[str]:
        """Handle a slash command.

        Args:
            command: The command name (without slash).
            args: Command arguments.
            context: Context dict with orchestrator state.

        Returns:
            Optional response message, or None if not handled.
        """
        # Default implementation - can be overridden
        return None
