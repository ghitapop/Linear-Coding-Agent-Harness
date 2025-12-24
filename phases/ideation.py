"""Ideation phase - transforms ideas into structured requirements."""

import json
from pathlib import Path
from typing import Any, Optional

from phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern


class IdeationPhase(Phase):
    """Phase 1: Ideation - Transform idea into requirements.

    This phase:
    - Takes a raw idea/concept from the user
    - Brainstorms requirements, use cases, and constraints
    - Identifies edge cases and potential issues
    - Produces a structured requirements document

    Supports swarm pattern with 3 specialized agents:
    - Agent 1: Focus on user requirements & use cases
    - Agent 2: Focus on technical feasibility & constraints
    - Agent 3: Focus on edge cases & potential issues
    """

    name = "ideation"
    display_name = "Ideation"
    description = "Transform idea into structured requirements"

    def __init__(self, config: Optional[PhaseConfig] = None) -> None:
        """Initialize the ideation phase.

        Args:
            config: Phase configuration. Defaults to swarm pattern.
        """
        if config is None:
            config = PhaseConfig(
                pattern=PlanningPattern.SWARM,
                checkpoint_pause=True,  # Pause for user approval
            )
        super().__init__(config)

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the ideation phase.

        Note: When swarm pattern is configured, the PhaseRunner will
        automatically use the SwarmController. This method handles
        single-agent execution.

        Args:
            input_data: The initial idea/concept from user.
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            PhaseResult with structured requirements.
        """
        from client import create_client
        from prompts import load_phase_prompt

        if not input_data:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="No idea provided. Please provide an initial concept.",
            )

        # Ensure project directory exists
        project_dir.mkdir(parents=True, exist_ok=True)

        # Get the brainstorm prompt
        try:
            prompt_template = load_phase_prompt("ideation", "brainstorm")
        except FileNotFoundError:
            # Fallback to inline prompt
            prompt_template = self._get_default_prompt()

        # Inject the idea into the prompt
        prompt = prompt_template.replace("{{IDEA}}", str(input_data))

        # Check for error recovery context (retry with hint)
        if context and "recovery_hint" in context:
            prompt = f"""## Recovery Context
{context["recovery_hint"]}

---

{prompt}"""

        # Create and run the agent
        model = self.config.model
        client = create_client(project_dir, model)

        try:
            async with client:
                await client.query(prompt)

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

            # Record progress if error recovery is available
            if context and "error_recovery" in context:
                context["error_recovery"].record_progress()

            # Save requirements to file
            requirements_file = project_dir / "requirements.md"
            requirements_file.write_text(response_text)

            return PhaseResult(
                status=PhaseStatus.NEEDS_APPROVAL if self.config.checkpoint_pause else PhaseStatus.SUCCESS,
                output={"requirements": response_text, "idea": str(input_data)},
                output_reference=str(requirements_file),
                metadata={"pattern": self.config.pattern.value},
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def get_prompts(self) -> list[str]:
        """Get prompts for ideation phase.

        For swarm pattern, returns 3 specialized prompts.
        For single pattern, returns 1 comprehensive prompt.

        Returns:
            List of prompt strings.
        """
        from prompts import load_phase_prompt

        if self.config.pattern == PlanningPattern.SWARM:
            try:
                return [
                    load_phase_prompt("ideation", "brainstorm_user"),
                    load_phase_prompt("ideation", "brainstorm_technical"),
                    load_phase_prompt("ideation", "brainstorm_edge_cases"),
                ]
            except FileNotFoundError:
                # Fallback to single prompt
                pass

        try:
            return [load_phase_prompt("ideation", "brainstorm")]
        except FileNotFoundError:
            return [self._get_default_prompt()]

    async def validate_input(
        self,
        input_data: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Validate that an idea was provided.

        Args:
            input_data: The idea to validate.
            context: Optional context dict.

        Returns:
            True if idea is valid.
        """
        if not input_data:
            return False
        if isinstance(input_data, str) and len(input_data.strip()) < 10:
            return False
        return True

    def _get_default_prompt(self) -> str:
        """Get the default brainstorm prompt."""
        return """# Ideation Phase - Requirements Brainstorming

## Your Task
Analyze the following idea and produce a comprehensive requirements document.

## The Idea
{{IDEA}}

## Instructions

1. **Understand the Core Concept**
   - What is the main purpose of this application?
   - Who are the target users?
   - What problem does it solve?

2. **Define User Requirements**
   - List all user-facing features
   - Describe user workflows and journeys
   - Identify user personas if applicable

3. **Technical Requirements**
   - What data needs to be stored?
   - What integrations might be needed?
   - Performance requirements
   - Security considerations

4. **Edge Cases & Constraints**
   - What could go wrong?
   - Error handling scenarios
   - Scalability considerations
   - Accessibility requirements

5. **Success Criteria**
   - How will we know the project is complete?
   - What are the MVP features vs nice-to-haves?

## Output Format
Write a structured requirements document in Markdown format. Save it as `requirements.md` in the project directory.

The document should include:
- Executive Summary
- User Stories
- Functional Requirements
- Non-Functional Requirements
- Constraints & Assumptions
- Success Metrics
"""
