"""Architecture phase - transforms requirements into technical architecture."""

from pathlib import Path
from typing import Any, Optional

from phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern


class ArchitecturePhase(Phase):
    """Phase 2: Architecture - Transform requirements into technical design.

    This phase:
    - Takes structured requirements from ideation phase
    - Designs system architecture and component structure
    - Selects technology stack
    - Defines data models and API contracts
    - Produces architecture documentation

    Supports swarm pattern with 3 specialized agents:
    - Agent 1: System design and component architecture
    - Agent 2: Data models and database schema
    - Agent 3: API design and integrations
    """

    name = "architecture"
    display_name = "Architecture"
    description = "Design system architecture and select technology stack"

    def __init__(self, config: Optional[PhaseConfig] = None) -> None:
        """Initialize the architecture phase.

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
        """Run the architecture phase.

        Note: When swarm pattern is configured, the PhaseRunner will
        automatically use the SwarmController. This method handles
        single-agent execution.

        Args:
            input_data: Requirements from ideation phase.
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            PhaseResult with architecture documentation.
        """
        from client import create_client
        from prompts import load_phase_prompt

        # Extract requirements from input
        requirements = self._extract_requirements(input_data, project_dir)
        if not requirements:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="No requirements found. Run ideation phase first.",
            )

        # Ensure project directory exists
        project_dir.mkdir(parents=True, exist_ok=True)

        # Get the system design prompt
        try:
            prompt_template = load_phase_prompt("architecture", "system_design")
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        # Inject requirements into the prompt
        prompt = prompt_template.replace("{{REQUIREMENTS}}", requirements)

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

            # Save architecture to file
            architecture_file = project_dir / "architecture.md"
            architecture_file.write_text(response_text)

            return PhaseResult(
                status=PhaseStatus.NEEDS_APPROVAL if self.config.checkpoint_pause else PhaseStatus.SUCCESS,
                output={
                    "architecture": response_text,
                    "requirements": requirements,
                },
                output_reference=str(architecture_file),
                metadata={"pattern": self.config.pattern.value},
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def _extract_requirements(self, input_data: Any, project_dir: Path) -> Optional[str]:
        """Extract requirements from input data or file.

        Args:
            input_data: Input from previous phase.
            project_dir: Project directory.

        Returns:
            Requirements string or None.
        """
        # Try to get from input_data
        if isinstance(input_data, dict) and "requirements" in input_data:
            return input_data["requirements"]

        if isinstance(input_data, str) and len(input_data) > 50:
            return input_data

        # Try to read from file
        requirements_file = project_dir / "requirements.md"
        if requirements_file.exists():
            return requirements_file.read_text()

        return None

    def get_prompts(self) -> list[str]:
        """Get prompts for architecture phase.

        For swarm pattern, returns 3 specialized prompts.
        For single pattern, returns 1 comprehensive prompt.

        Returns:
            List of prompt strings.
        """
        from prompts import load_phase_prompt

        if self.config.pattern == PlanningPattern.SWARM:
            try:
                return [
                    load_phase_prompt("architecture", "system_design"),
                    load_phase_prompt("architecture", "data_models"),
                    load_phase_prompt("architecture", "api_design"),
                ]
            except FileNotFoundError:
                pass

        try:
            return [load_phase_prompt("architecture", "system_design")]
        except FileNotFoundError:
            return [self._get_default_prompt()]

    async def validate_input(
        self,
        input_data: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Validate that requirements are provided.

        Args:
            input_data: The requirements to validate.
            context: Optional context dict.

        Returns:
            True if requirements are valid.
        """
        if isinstance(input_data, dict) and "requirements" in input_data:
            return bool(input_data["requirements"])

        if isinstance(input_data, str) and len(input_data) > 50:
            return True

        # Check for requirements file
        if context and "project_dir" in context:
            req_file = Path(context["project_dir"]) / "requirements.md"
            return req_file.exists()

        return False

    def _get_default_prompt(self) -> str:
        """Get the default system design prompt."""
        return """# Architecture Phase - System Design

## Your Task
Design the technical architecture for the application based on the requirements below.

## Requirements
{{REQUIREMENTS}}

## Instructions

1. **Technology Stack Selection**
   - Choose frontend framework (React, Vue, Next.js, etc.)
   - Choose backend framework (Node.js, Python/FastAPI, Go, etc.)
   - Choose database (PostgreSQL, MongoDB, SQLite, etc.)
   - Justify each choice based on requirements

2. **System Architecture**
   - Draw component diagram (describe in text/ASCII)
   - Define service boundaries
   - Identify external dependencies
   - Plan for scalability

3. **Data Models**
   - Define core entities and relationships
   - Design database schema
   - Plan data validation rules
   - Consider data migration strategy

4. **API Design**
   - Define REST/GraphQL endpoints
   - Specify request/response formats
   - Plan authentication/authorization
   - Document error handling

5. **Project Structure**
   - Define directory structure
   - Plan file organization
   - Identify shared utilities
   - Set up configuration approach

## Output Format
Write an architecture document in Markdown format. Save it as `architecture.md` in the project directory.

The document should include:
- Technology Stack Overview
- System Architecture Diagram (ASCII)
- Data Models & Schema
- API Specification
- Directory Structure
- Security Considerations
- Deployment Strategy
"""
