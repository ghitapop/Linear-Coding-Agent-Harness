"""Implement phase - wraps the existing coding agent."""

from pathlib import Path
from typing import Any, Optional

from phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus


class ImplementPhase(Phase):
    """Phase 5: Implement features.

    This phase:
    - Queries Linear for next TODO issue
    - Claims the issue (marks In Progress)
    - Implements the feature
    - Tests via Puppeteer
    - Marks issue Done
    - Updates META issue

    It wraps the existing coding agent functionality.
    This phase runs iteratively until all work items are done.
    """

    name = "implement"
    display_name = "Implement"
    description = "Implement features from work items"

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        max_sessions: int = 1000,
        auto_continue_delay: int = 3,
    ) -> None:
        """Initialize the implement phase.

        Args:
            config: Phase configuration.
            max_sessions: Maximum number of agent sessions.
            auto_continue_delay: Seconds to wait between sessions.
        """
        super().__init__(config)
        self.max_sessions = max_sessions
        self.auto_continue_delay = auto_continue_delay
        self._session_count = 0

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the implement phase.

        This runs a single implementation session. Call repeatedly
        to implement multiple work items.

        Args:
            input_data: Previous phase output (not typically used).
            project_dir: Project directory path.
            context: Optional context dict with shutdown handler.

        Returns:
            PhaseResult with implementation status.
        """
        import asyncio

        # Import here to avoid circular imports
        from client import create_client
        from prompts import get_coding_prompt
        from progress import is_linear_initialized, print_progress_summary

        # Check prerequisites
        if not is_linear_initialized(project_dir):
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="Project not initialized. Run initialize phase first.",
            )

        # Check session limit
        if self._session_count >= self.max_sessions:
            return PhaseResult(
                status=PhaseStatus.SUCCESS,
                output="Reached maximum session count",
                metadata={"sessions_run": self._session_count},
            )

        # Check for shutdown request
        shutdown_handler = context.get("shutdown_handler") if context else None
        if shutdown_handler and shutdown_handler.check_should_stop():
            return PhaseResult(
                status=PhaseStatus.NEEDS_APPROVAL,
                output="Shutdown requested",
                metadata={"shutdown": True},
            )

        # Get the coding prompt
        prompt = get_coding_prompt()

        # Create and run the agent
        model = self.config.model
        client = create_client(project_dir, model)

        try:
            self._session_count += 1

            async with client:
                # Send the query
                await client.query(prompt)

                # Collect response
                response_text = ""
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if hasattr(block, "text"):
                                response_text += block.text
                                print(block.text, end="", flush=True)
                            elif hasattr(block, "name"):
                                print(f"\n[Tool: {block.name}]", flush=True)

                print()

            # Print progress
            print_progress_summary(project_dir)

            return PhaseResult(
                status=PhaseStatus.SUCCESS,
                output=response_text,
                metadata={
                    "session_number": self._session_count,
                    "continue": True,  # Signal that more work may be needed
                },
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
                metadata={"session_number": self._session_count},
            )

    async def run_until_complete(
        self,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run implementation sessions until complete or stopped.

        Args:
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            Final PhaseResult.
        """
        import asyncio

        shutdown_handler = context.get("shutdown_handler") if context else None
        last_result: Optional[PhaseResult] = None

        while self._session_count < self.max_sessions:
            # Check for shutdown
            if shutdown_handler and shutdown_handler.check_should_stop():
                break

            # Run a session
            result = await self.run(None, project_dir, context)
            last_result = result

            if result.is_failed:
                # On error, wait and retry
                await asyncio.sleep(self.auto_continue_delay)
                continue

            if not result.metadata.get("continue", False):
                # No more work
                break

            # Wait before next session
            await asyncio.sleep(self.auto_continue_delay)

        return last_result or PhaseResult(
            status=PhaseStatus.SUCCESS,
            output="No sessions run",
        )

    def should_skip(self, context: Optional[dict[str, Any]] = None) -> bool:
        """Check if implementation should be skipped.

        Args:
            context: Context dict.

        Returns:
            True if should skip.
        """
        if not self.config.enabled:
            return True

        # Check if there's work to do
        if context and "project_dir" in context:
            from progress import is_linear_initialized

            project_dir = Path(context["project_dir"])
            if not is_linear_initialized(project_dir):
                # Can't implement without initialization
                return True

        return False

    def get_prompts(self) -> list[str]:
        """Get the coding prompt.

        Returns:
            List with single coding prompt.
        """
        from prompts import get_coding_prompt

        return [get_coding_prompt()]

    def reset_session_count(self) -> None:
        """Reset the session counter."""
        self._session_count = 0

    @property
    def sessions_run(self) -> int:
        """Get number of sessions run."""
        return self._session_count
