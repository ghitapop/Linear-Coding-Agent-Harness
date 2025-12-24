"""Testing phase - comprehensive testing of implemented features."""

from pathlib import Path
from typing import Any, Optional

from phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern


class TestingPhase(Phase):
    """Phase 6: Testing - Comprehensive testing of the application.

    This phase:
    - Runs after implementation is complete
    - Executes unit, integration, and e2e tests
    - Validates all acceptance criteria
    - Uses Puppeteer for UI testing
    - Produces a test report

    Runs with single agent pattern for consistency.
    """

    name = "testing"
    display_name = "Testing"
    description = "Comprehensive testing of implemented features"

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        run_e2e: bool = True,
        run_unit: bool = True,
        run_integration: bool = True,
    ) -> None:
        """Initialize the testing phase.

        Args:
            config: Phase configuration.
            run_e2e: Whether to run e2e tests.
            run_unit: Whether to run unit tests.
            run_integration: Whether to run integration tests.
        """
        if config is None:
            config = PhaseConfig(
                pattern=PlanningPattern.SINGLE,
                checkpoint_pause=False,  # Don't pause, just report results
                timeout_minutes=120,  # Tests may take longer
            )
        super().__init__(config)
        self.run_e2e = run_e2e
        self.run_unit = run_unit
        self.run_integration = run_integration

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the testing phase.

        Args:
            input_data: Output from implementation phase (optional).
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            PhaseResult with test results.
        """
        from client import create_client
        from prompts import load_phase_prompt

        # Ensure project directory exists and has code
        if not project_dir.exists():
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="Project directory does not exist.",
            )

        # Get the test plan prompt
        try:
            prompt_template = load_phase_prompt("testing", "test_plan")
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        # Configure test types
        test_types = []
        if self.run_unit:
            test_types.append("unit")
        if self.run_integration:
            test_types.append("integration")
        if self.run_e2e:
            test_types.append("e2e")

        prompt = prompt_template.replace("{{TEST_TYPES}}", ", ".join(test_types))
        prompt = prompt.replace("{{PROJECT_DIR}}", str(project_dir))

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

            # Parse test results
            test_results = self._parse_test_results(response_text)

            # Save test report
            report_file = project_dir / "test_report.md"
            report_file.write_text(response_text)

            # Determine status based on results
            if test_results["failed"] > 0:
                status = PhaseStatus.FAILED
            else:
                status = PhaseStatus.SUCCESS

            return PhaseResult(
                status=status,
                output={
                    "report": response_text,
                    "results": test_results,
                },
                output_reference=str(report_file),
                metadata={
                    "passed": test_results["passed"],
                    "failed": test_results["failed"],
                    "skipped": test_results["skipped"],
                    "test_types": test_types,
                },
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def _parse_test_results(self, response_text: str) -> dict[str, int]:
        """Parse test results from response.

        Args:
            response_text: The response containing test output.

        Returns:
            Dict with passed/failed/skipped counts.
        """
        results = {"passed": 0, "failed": 0, "skipped": 0}

        # Look for common test result patterns
        text_lower = response_text.lower()

        # Try to find pytest-style output
        for line in response_text.split("\n"):
            line_lower = line.lower()
            if "passed" in line_lower:
                try:
                    # Extract number before "passed"
                    parts = line_lower.split("passed")
                    if parts[0]:
                        num = "".join(c for c in parts[0].split()[-1] if c.isdigit())
                        if num:
                            results["passed"] = int(num)
                except (ValueError, IndexError):
                    pass

            if "failed" in line_lower:
                try:
                    parts = line_lower.split("failed")
                    if parts[0]:
                        num = "".join(c for c in parts[0].split()[-1] if c.isdigit())
                        if num:
                            results["failed"] = int(num)
                except (ValueError, IndexError):
                    pass

            if "skipped" in line_lower:
                try:
                    parts = line_lower.split("skipped")
                    if parts[0]:
                        num = "".join(c for c in parts[0].split()[-1] if c.isdigit())
                        if num:
                            results["skipped"] = int(num)
                except (ValueError, IndexError):
                    pass

        # Look for checkmarks and X marks
        results["passed"] += response_text.count("✓")
        results["passed"] += response_text.count("✔")
        results["passed"] += response_text.count("[PASS]")
        results["failed"] += response_text.count("✗")
        results["failed"] += response_text.count("✘")
        results["failed"] += response_text.count("[FAIL]")

        return results

    def get_prompts(self) -> list[str]:
        """Get prompts for testing phase.

        Returns:
            List with single test plan prompt.
        """
        from prompts import load_phase_prompt

        try:
            return [load_phase_prompt("testing", "test_plan")]
        except FileNotFoundError:
            return [self._get_default_prompt()]

    def should_skip(self, context: Optional[dict[str, Any]] = None) -> bool:
        """Check if testing should be skipped.

        Args:
            context: Context dict.

        Returns:
            True if should skip.
        """
        if not self.config.enabled:
            return True

        # Check if project has any code to test
        if context and "project_dir" in context:
            project_dir = Path(context["project_dir"])
            # Look for common source directories
            source_dirs = ["src", "app", "lib", "components"]
            has_code = any((project_dir / d).exists() for d in source_dirs)
            if not has_code:
                # Check for any .py, .js, .ts files
                has_code = bool(list(project_dir.glob("**/*.py"))) or \
                           bool(list(project_dir.glob("**/*.js"))) or \
                           bool(list(project_dir.glob("**/*.ts")))
            return not has_code

        return False

    def _get_default_prompt(self) -> str:
        """Get the default test plan prompt."""
        return """# Testing Phase - Comprehensive Testing

## Your Task
Run comprehensive tests on the implemented application. Execute {{TEST_TYPES}} tests.

## Instructions

1. **Discover Test Files**
   - Find existing test files in the project
   - Identify testing framework used (pytest, jest, vitest, etc.)
   - Check for test configuration files

2. **Run Unit Tests**
   - Execute unit tests for all modules
   - Report pass/fail counts
   - Document any failures with details

3. **Run Integration Tests**
   - Test API endpoints
   - Test database operations
   - Test service interactions

4. **Run E2E Tests** (if Puppeteer available)
   - Navigate to application URL
   - Test critical user flows
   - Take screenshots of key pages
   - Verify UI rendering

5. **Validate Acceptance Criteria**
   - Review tasks.md for acceptance criteria
   - Manually verify each criterion
   - Document any unmet criteria

6. **Generate Test Report**
   Create a comprehensive report with:
   - Summary statistics
   - Detailed failure analysis
   - Coverage information (if available)
   - Recommendations for fixes

## Output Format
Save the test report as `test_report.md` with:

```markdown
# Test Report

## Summary
- **Total Tests:** X
- **Passed:** Y ✓
- **Failed:** Z ✗
- **Skipped:** W

## Unit Tests
[Details...]

## Integration Tests
[Details...]

## E2E Tests
[Details with screenshots...]

## Failures Analysis
[Details of each failure...]

## Recommendations
[What needs to be fixed...]
```

## Important
- Run ALL tests, not just a sample
- If tests fail, document the exact error
- If no tests exist, recommend creating them
- Use Puppeteer for browser-based testing
"""
