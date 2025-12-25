"""Task breakdown phase - decomposes architecture into implementable work items."""

import json
from pathlib import Path
from typing import Any, Optional

from server.harness_agent.phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern


class TaskBreakdownPhase(Phase):
    """Phase 3: Task Breakdown - Decompose architecture into work items.

    This phase:
    - Takes architecture documentation from previous phase
    - Breaks down into 50-200+ granular, implementable tasks
    - Assigns priorities and dependencies
    - Creates work items in the configured backend (Linear/JSON)
    - Produces a structured feature list

    This phase typically runs with single agent pattern
    as it requires consistent task organization.
    """

    name = "task_breakdown"
    display_name = "Task Breakdown"
    description = "Decompose architecture into implementable work items"

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        min_tasks: int = 50,
        max_tasks: int = 200,
    ) -> None:
        """Initialize the task breakdown phase.

        Args:
            config: Phase configuration. Defaults to single pattern.
            min_tasks: Minimum number of tasks to generate.
            max_tasks: Maximum number of tasks to generate.
        """
        if config is None:
            config = PhaseConfig(
                pattern=PlanningPattern.SINGLE,
                checkpoint_pause=True,  # Pause for user review
            )
        super().__init__(config)
        self.min_tasks = min_tasks
        self.max_tasks = max_tasks

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the task breakdown phase.

        Args:
            input_data: Architecture from previous phase.
            project_dir: Project directory path.
            context: Optional context dict with work_tracker.

        Returns:
            PhaseResult with task list.
        """
        from agents.client import create_client
        from server.utils.prompts import load_phase_prompt

        # Extract architecture from input
        architecture = self._extract_architecture(input_data, project_dir)
        if not architecture:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="No architecture found. Run architecture phase first.",
            )

        # Also get requirements if available
        requirements = self._extract_requirements(input_data, project_dir)

        # Ensure project directory exists
        project_dir.mkdir(parents=True, exist_ok=True)

        # Get the decompose prompt
        try:
            prompt_template = load_phase_prompt("task_breakdown", "decompose")
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        # Inject architecture into the prompt
        prompt = prompt_template.replace("{{ARCHITECTURE}}", architecture)
        prompt = prompt.replace("{{REQUIREMENTS}}", requirements or "See architecture document.")
        prompt = prompt.replace("{{MIN_TASKS}}", str(self.min_tasks))
        prompt = prompt.replace("{{MAX_TASKS}}", str(self.max_tasks))

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

            # Save task breakdown to file in PRPs/plans/ subdirectory
            plans_dir = project_dir / "PRPs" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            tasks_file = plans_dir / "tasks.md"
            tasks_file.write_text(response_text, encoding="utf-8")

            # Try to parse task count from response
            task_count = self._count_tasks(response_text)

            return PhaseResult(
                status=PhaseStatus.NEEDS_APPROVAL if self.config.checkpoint_pause else PhaseStatus.SUCCESS,
                output={
                    "tasks": response_text,
                    "task_count": task_count,
                    "architecture": architecture,
                },
                output_reference=str(tasks_file),
                metadata={
                    "task_count": task_count,
                    "min_required": self.min_tasks,
                },
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def _extract_architecture(self, input_data: Any, project_dir: Path) -> Optional[str]:
        """Extract architecture from input data or file.

        Args:
            input_data: Input from previous phase.
            project_dir: Project directory.

        Returns:
            Architecture string or None.
        """
        # Try to get from input_data
        if isinstance(input_data, dict) and "architecture" in input_data:
            return input_data["architecture"]

        if isinstance(input_data, str) and len(input_data) > 100:
            return input_data

        # Try to read from file in PRPs/plans/ subdirectory
        architecture_file = project_dir / "PRPs" / "plans" / "architecture.md"
        if architecture_file.exists():
            return architecture_file.read_text(encoding="utf-8")

        return None

    def _extract_requirements(self, input_data: Any, project_dir: Path) -> Optional[str]:
        """Extract requirements from input data or file.

        Args:
            input_data: Input from previous phase.
            project_dir: Project directory.

        Returns:
            Requirements string or None.
        """
        if isinstance(input_data, dict) and "requirements" in input_data:
            return input_data["requirements"]

        # Try to read from file in PRPs/plans/ subdirectory
        requirements_file = project_dir / "PRPs" / "plans" / "requirements.md"
        if requirements_file.exists():
            return requirements_file.read_text(encoding="utf-8")

        return None

    def _count_tasks(self, response_text: str) -> int:
        """Count tasks in the response.

        Args:
            response_text: The response containing tasks.

        Returns:
            Estimated task count.
        """
        # Count lines that look like task items
        count = 0
        for line in response_text.split("\n"):
            line = line.strip()
            # Count markdown list items, numbered items, or task patterns
            if (
                line.startswith("- [ ]")
                or line.startswith("* [ ]")
                or (line and line[0].isdigit() and "." in line[:5])
                or line.startswith("### Task")
                or line.startswith("## Task")
            ):
                count += 1
        return count

    def get_prompts(self) -> list[str]:
        """Get prompts for task breakdown phase.

        Returns:
            List with single decompose prompt.
        """
        from prompts import load_phase_prompt

        try:
            return [load_phase_prompt("task_breakdown", "decompose")]
        except FileNotFoundError:
            return [self._get_default_prompt()]

    async def validate_input(
        self,
        input_data: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Validate that architecture is provided.

        Args:
            input_data: The architecture to validate.
            context: Optional context dict.

        Returns:
            True if architecture is valid.
        """
        if isinstance(input_data, dict) and "architecture" in input_data:
            return bool(input_data["architecture"])

        if isinstance(input_data, str) and len(input_data) > 100:
            return True

        if context and "project_dir" in context:
            arch_file = Path(context["project_dir"]) / "architecture.md"
            return arch_file.exists()

        return False

    def _get_default_prompt(self) -> str:
        """Get the default decompose prompt."""
        return """# Task Breakdown Phase - Feature Decomposition

## Your Task
Break down the architecture into {{MIN_TASKS}}-{{MAX_TASKS}} granular, implementable tasks.

## Architecture
{{ARCHITECTURE}}

## Requirements Reference
{{REQUIREMENTS}}

## Instructions

1. **Identify Major Components**
   - List all major system components
   - Group related functionality
   - Identify shared dependencies

2. **Break Down Each Component**
   For each component, create tasks for:
   - Setup/scaffolding
   - Core logic implementation
   - Data models/schema
   - API endpoints
   - UI components
   - Tests
   - Documentation

3. **Task Requirements**
   Each task should:
   - Be completable in 1-4 hours by a skilled developer
   - Have a clear definition of done
   - Be atomic (not dependent on unfinished work)
   - Include acceptance criteria

4. **Assign Priorities**
   - P1 (Urgent): Core infrastructure, blocking dependencies
   - P2 (High): Primary features, critical path
   - P3 (Medium): Secondary features, enhancements
   - P4 (Low): Nice-to-haves, polish

5. **Define Dependencies**
   - Mark which tasks depend on others
   - Ensure no circular dependencies
   - Group into implementation phases

## Output Format
Create tasks in the following format and save as `tasks.md`:

```markdown
# Task Breakdown

## Phase 1: Foundation (P1)

### Task 1.1: Project Setup
**Priority:** P1 (Urgent)
**Estimate:** 1 hour
**Dependencies:** None
**Description:** Initialize project with chosen framework...
**Acceptance Criteria:**
- [ ] Project structure created
- [ ] Dependencies installed
- [ ] Dev server runs

### Task 1.2: Database Schema
...

## Phase 2: Core Features (P2)
...
```

**IMPORTANT:** Generate at least {{MIN_TASKS}} tasks. Be thorough and granular.
Each task should be specific enough that any developer could pick it up and complete it.
"""
