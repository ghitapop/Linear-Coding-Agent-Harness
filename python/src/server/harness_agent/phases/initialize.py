"""Initialize phase - wraps the existing initializer agent."""

from pathlib import Path
from typing import Any, Optional

from server.harness_agent.phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus


class InitializePhase(Phase):
    """Phase 4: Initialize the project.

    This phase:
    - Creates Linear project with issues
    - Sets up project structure
    - Creates init.sh script
    - Initializes git repository
    - Writes .linear_project.json marker

    It wraps the existing initializer agent functionality.
    """

    name = "initialize"
    display_name = "Initialize"
    description = "Set up project structure and create Linear issues"

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the initialize phase.

        Args:
            input_data: Architecture/requirements from previous phases.
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            PhaseResult with initialization status.
        """
        # Import here to avoid circular imports
        from agents.client import create_client
        from server.utils.prompts import copy_spec_to_project, get_initializer_prompt
        from server.autonomous_agent.progress import is_linear_initialized

        # Check if already initialized
        if is_linear_initialized(project_dir):
            return PhaseResult(
                status=PhaseStatus.SKIPPED,
                output="Project already initialized",
                metadata={"reason": "linear_already_initialized"},
            )

        # Ensure project directory exists
        project_dir.mkdir(parents=True, exist_ok=True)

        # Copy app spec to project directory
        copy_spec_to_project(project_dir)

        # Get the initializer prompt
        prompt = get_initializer_prompt()

        # If we have input data from previous phases, augment the prompt
        if input_data:
            if isinstance(input_data, dict):
                if "requirements" in input_data:
                    prompt = f"## Requirements\n{input_data['requirements']}\n\n{prompt}"
                if "architecture" in input_data:
                    prompt = f"## Architecture\n{input_data['architecture']}\n\n{prompt}"

        # Create and run the agent
        model = self.config.model
        client = create_client(project_dir, model)

        try:
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

            # Check if initialization succeeded
            if is_linear_initialized(project_dir):
                return PhaseResult(
                    status=PhaseStatus.SUCCESS,
                    output=response_text,
                    output_reference=str(project_dir / ".linear_project.json"),
                    metadata={"initialized": True},
                )
            else:
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    output=response_text,
                    error="Linear project was not initialized",
                )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def should_skip(self, context: Optional[dict[str, Any]] = None) -> bool:
        """Check if initialization should be skipped.

        Args:
            context: Context dict with project_dir.

        Returns:
            True if already initialized.
        """
        if not self.config.enabled:
            return True

        # Check if project_dir is in context
        if context and "project_dir" in context:
            from progress import is_linear_initialized

            project_dir = Path(context["project_dir"])
            if is_linear_initialized(project_dir):
                return True

        return False

    def get_prompts(self) -> list[str]:
        """Get the initializer prompt.

        Returns:
            List with single initializer prompt.
        """
        from prompts import get_initializer_prompt

        return [get_initializer_prompt()]
