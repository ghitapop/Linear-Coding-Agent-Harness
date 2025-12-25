"""Deploy phase - optional deployment of the application."""

from pathlib import Path
from typing import Any, Optional

from server.harness_agent.phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern


class DeployPhase(Phase):
    """Phase 7: Deploy - Optional deployment of the application.

    This phase:
    - Runs after testing passes
    - Prepares application for deployment
    - Creates deployment configuration
    - Optionally deploys to target environment
    - Produces deployment documentation

    This phase is optional and disabled by default.
    """

    name = "deploy"
    display_name = "Deploy"
    description = "Deploy the application to target environment"

    def __init__(
        self,
        config: Optional[PhaseConfig] = None,
        target: str = "docker",
        auto_deploy: bool = False,
    ) -> None:
        """Initialize the deploy phase.

        Args:
            config: Phase configuration. Disabled by default.
            target: Deployment target (docker, vercel, railway, etc.)
            auto_deploy: Whether to actually deploy or just prepare.
        """
        if config is None:
            config = PhaseConfig(
                enabled=False,  # Disabled by default
                pattern=PlanningPattern.SINGLE,
                checkpoint_pause=True,  # Always pause before deploying
            )
        super().__init__(config)
        self.target = target
        self.auto_deploy = auto_deploy

    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the deploy phase.

        Args:
            input_data: Test results from previous phase.
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            PhaseResult with deployment status.
        """
        from client import create_client
        from prompts import load_phase_prompt

        # Check if tests passed
        if isinstance(input_data, dict):
            test_results = input_data.get("results", {})
            if test_results.get("failed", 0) > 0:
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    error="Cannot deploy: tests failed. Fix failing tests first.",
                    metadata={"test_failures": test_results.get("failed", 0)},
                )

        # Ensure project directory exists
        if not project_dir.exists():
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error="Project directory does not exist.",
            )

        # Get the deploy prompt
        try:
            prompt_template = load_phase_prompt("deploy", "deploy")
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        # Configure deployment
        prompt = prompt_template.replace("{{TARGET}}", self.target)
        prompt = prompt.replace("{{AUTO_DEPLOY}}", str(self.auto_deploy).lower())
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

            # Save deployment documentation
            deploy_file = project_dir / "DEPLOYMENT.md"
            deploy_file.write_text(response_text)

            # Check for deployment success indicators
            deployed = self._check_deployment_success(response_text)

            return PhaseResult(
                status=PhaseStatus.SUCCESS,
                output={
                    "documentation": response_text,
                    "target": self.target,
                    "deployed": deployed,
                },
                output_reference=str(deploy_file),
                metadata={
                    "target": self.target,
                    "deployed": deployed,
                    "auto_deploy": self.auto_deploy,
                },
            )

        except Exception as e:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                error=str(e),
            )

    def _check_deployment_success(self, response_text: str) -> bool:
        """Check if deployment was successful.

        Args:
            response_text: The response text to check.

        Returns:
            True if deployment indicators found.
        """
        success_indicators = [
            "deployed successfully",
            "deployment complete",
            "live at",
            "available at",
            "running at",
            "deployed to",
        ]
        text_lower = response_text.lower()
        return any(indicator in text_lower for indicator in success_indicators)

    def get_prompts(self) -> list[str]:
        """Get prompts for deploy phase.

        Returns:
            List with single deploy prompt.
        """
        from prompts import load_phase_prompt

        try:
            return [load_phase_prompt("deploy", "deploy")]
        except FileNotFoundError:
            return [self._get_default_prompt()]

    def should_skip(self, context: Optional[dict[str, Any]] = None) -> bool:
        """Check if deployment should be skipped.

        Args:
            context: Context dict.

        Returns:
            True if should skip.
        """
        # Skip if explicitly disabled
        if not self.config.enabled:
            return True

        # Skip if tests failed
        if context and "test_results" in context:
            results = context["test_results"]
            if isinstance(results, dict) and results.get("failed", 0) > 0:
                return True

        return False

    def _get_default_prompt(self) -> str:
        """Get the default deploy prompt."""
        return """# Deploy Phase - Application Deployment

## Your Task
Prepare and optionally deploy the application to {{TARGET}}.

## Configuration
- **Target:** {{TARGET}}
- **Auto Deploy:** {{AUTO_DEPLOY}}

## Instructions

1. **Analyze Project Type**
   - Detect the framework and language
   - Identify required build steps
   - Check for existing deployment config

2. **Create Deployment Configuration**
   Based on target "{{TARGET}}":

   **For Docker:**
   - Create/update Dockerfile
   - Create docker-compose.yml if needed
   - Configure environment variables
   - Set up health checks

   **For Vercel:**
   - Create/update vercel.json
   - Configure build settings
   - Set up environment variables

   **For Railway:**
   - Create railway.json or Procfile
   - Configure build settings
   - Set up environment variables

   **For Generic:**
   - Create deployment scripts
   - Document manual deployment steps

3. **Build & Test Deployment Locally**
   - Run the build process
   - Test the deployment configuration
   - Verify the application starts correctly

4. **Deploy (if auto_deploy is true)**
   - Only if auto_deploy is enabled
   - Execute deployment commands
   - Verify deployment succeeded
   - Report deployment URL

5. **Create Documentation**
   Create comprehensive deployment docs:

## Output Format
Save deployment documentation as `DEPLOYMENT.md`:

```markdown
# Deployment Guide

## Prerequisites
- [List required tools]

## Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| ... | ... | ... |

## Local Development
```bash
# Commands to run locally
```

## Build
```bash
# Build commands
```

## Deploy
```bash
# Deployment commands
```

## Verify
- [ ] Application loads
- [ ] API endpoints respond
- [ ] Database connected

## Rollback
```bash
# How to rollback if needed
```

## URLs
- Production: [URL if deployed]
- Staging: [URL if applicable]
```

## Important
- NEVER expose secrets in documentation
- Use environment variables for all secrets
- Test deployment locally before pushing
- Document rollback procedures
"""
