"""Phase runner for sequential phase execution."""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from server.harness_agent.orchestrator.aggregator import AggregationStrategy, create_aggregator
from server.harness_agent.orchestrator.error_recovery import (
    ErrorRecoveryManager,
    RecoveryAction,
    create_recovery_manager_from_config,
)
from server.harness_agent.orchestrator.keyboard_handler import get_keyboard_handler, is_interrupt_requested, clear_interrupt
from server.harness_agent.orchestrator.shutdown import GracefulShutdown
from server.harness_agent.orchestrator.state_machine import PhaseStatus, PipelineStatus, StateMachine
from server.harness_agent.orchestrator.swarm_controller import (
    AgentStatus,
    SwarmController,
    SwarmAgentConfig,
    create_architecture_swarm_configs,
    create_ideation_swarm_configs,
)
from server.harness_agent.phases.base import Phase, PhaseConfig, PhaseResult, PlanningPattern
from server.harness_agent.phases.base import PhaseStatus as PhaseResultStatus


class InterruptError(Exception):
    """Raised when an interrupt is requested."""
    pass


class PhaseRunner:
    """Runs phases sequentially with state persistence.

    This is the main orchestration loop that:
    - Determines which phase to run next
    - Executes phases with retry logic
    - Handles checkpoints and approvals
    - Persists state after each phase
    """

    def __init__(
        self,
        state_machine: StateMachine,
        shutdown_handler: Optional[GracefulShutdown] = None,
        error_recovery: Optional[ErrorRecoveryManager] = None,
        swarm_controller: Optional[SwarmController] = None,
    ) -> None:
        """Initialize the phase runner.

        Args:
            state_machine: State machine for persistence.
            shutdown_handler: Optional shutdown handler.
            error_recovery: Optional error recovery manager.
            swarm_controller: Optional swarm controller for parallel agents.
        """
        self._state_machine = state_machine
        self._shutdown_handler = shutdown_handler
        self._error_recovery = error_recovery or ErrorRecoveryManager()
        self._swarm_controller = swarm_controller or SwarmController()
        self._phases: dict[str, Phase] = {}

    def register_phase(self, phase: Phase) -> None:
        """Register a phase.

        Args:
            phase: Phase to register.
        """
        self._phases[phase.name] = phase

    def register_phases(self, phases: list[Phase]) -> None:
        """Register multiple phases.

        Args:
            phases: List of phases to register.
        """
        for phase in phases:
            self.register_phase(phase)

    async def run_until_complete(
        self,
        project_dir: Path,
        input_data: Optional[Any] = None,
        approval_callback: Optional[Any] = None,
    ) -> bool:
        """Run all phases until completion or stop.

        Args:
            project_dir: Project directory.
            input_data: Initial input data.
            approval_callback: Optional callback for checkpoint approvals.

        Returns:
            True if all phases completed successfully.
        """
        # Set pipeline to running
        self._state_machine.set_status(PipelineStatus.RUNNING)

        # Build context
        context: dict[str, Any] = {
            "project_dir": str(project_dir),
            "shutdown_handler": self._shutdown_handler,
            "approval_callback": approval_callback,
            "error_recovery": self._error_recovery,
            "swarm_controller": self._swarm_controller,
            "rejection_feedback": self._state_machine.get_rejection_feedback(),
        }

        # Reset error recovery for fresh run
        self._error_recovery.reset()

        # Current input for phase chaining
        current_input = input_data

        # Run phases in order
        while True:
            # Check for keyboard interrupt (ESC or CTRL+C)
            if is_interrupt_requested():
                print("\n[INTERRUPT] Operation interrupted by user")
                self._state_machine.set_status(PipelineStatus.PAUSED)
                clear_interrupt()
                return False

            # Check for shutdown
            if self._shutdown_handler and self._shutdown_handler.check_should_stop():
                self._state_machine.set_status(PipelineStatus.STOPPING)
                return False

            # Get next phase
            next_phase_name = self._state_machine.get_next_phase()
            if next_phase_name is None:
                # All phases complete
                break

            # Get phase instance
            phase = self._phases.get(next_phase_name)
            if phase is None:
                # Skip unknown phases
                self._state_machine.skip_phase(next_phase_name)
                continue

            # Check if phase should be skipped
            if phase.should_skip(context):
                self._state_machine.skip_phase(next_phase_name)
                continue

            # Run the phase
            result = await self._run_phase(phase, current_input, project_dir, context)

            # Handle result
            if result.is_success:
                self._state_machine.complete_phase(
                    next_phase_name,
                    output_reference=result.output_reference,
                )
                # Clear any previous rejection feedback on success
                self._state_machine.clear_rejection_feedback()
                # Chain output to next phase
                current_input = result.output

            elif result.needs_approval:
                # Handle checkpoint
                if approval_callback:
                    # approval_callback returns (approved: bool, feedback: Optional[str])
                    approval_result = await approval_callback(
                        result.output,
                        next_phase_name,
                    )
                    # Handle both old-style (bool) and new-style (tuple) callbacks
                    if isinstance(approval_result, tuple):
                        approved, feedback = approval_result
                    else:
                        approved, feedback = approval_result, None

                    if not approved:
                        # Store feedback for the retry
                        if feedback:
                            self._state_machine.set_rejection_feedback(feedback)
                            print(f"\n[FEEDBACK] Your feedback has been saved and will be incorporated on retry.")
                        # Reset phase to PENDING so it can be retried when resumed
                        # (otherwise get_next_phase() would skip this RUNNING phase
                        # and try to run the next phase with wrong input)
                        phase_state = self._state_machine.state.phases.get(next_phase_name)
                        if phase_state:
                            phase_state.status = PhaseStatus.PENDING
                            phase_state.started_at = None  # Clear for clean retry
                            phase_state.error = None
                        self._state_machine.set_status(PipelineStatus.PAUSED)
                        return False
                else:
                    # No approval callback, pause
                    # Reset phase to PENDING so it can be retried when resumed
                    phase_state = self._state_machine.state.phases.get(next_phase_name)
                    if phase_state:
                        phase_state.status = PhaseStatus.PENDING
                        phase_state.started_at = None  # Clear for clean retry
                        phase_state.error = None
                    self._state_machine.set_status(PipelineStatus.PAUSED)
                    return False

            elif result.is_failed:
                # Record error and get recovery decision
                error_msg = result.error or "Unknown error"
                self._error_recovery.record_error(
                    error_msg,
                    phase=next_phase_name,
                )
                decision = self._error_recovery.get_recovery_decision(
                    error_msg,
                    phase=next_phase_name,
                )

                # Check if we should abort or escalate
                if decision.action == RecoveryAction.ABORT:
                    self._state_machine.fail_phase(next_phase_name, error_msg)
                    self._state_machine.set_status(PipelineStatus.FAILED)
                    return False

                if decision.should_escalate:
                    # Pause for user intervention
                    self._state_machine.fail_phase(next_phase_name, error_msg)
                    self._state_machine.set_status(PipelineStatus.PAUSED)
                    print(f"\n[WARNING] Escalation required: {decision.hint or error_msg}")
                    return False

                # Check retry count
                phase_state = self._state_machine.state.phases.get(next_phase_name)
                if phase_state and phase_state.retry_count >= phase.config.max_retries:
                    self._state_machine.fail_phase(next_phase_name, "Max retries exceeded")
                    self._state_machine.set_status(PipelineStatus.FAILED)
                    return False

                # Apply recovery action
                if decision.action == RecoveryAction.RETRY_WITH_DELAY:
                    print(f"[DELAY] Waiting {decision.retry_delay_seconds}s before retry...")
                    await asyncio.sleep(decision.retry_delay_seconds)

                if decision.hint:
                    print(f"[HINT] Recovery hint: {decision.hint}")

                # Increment retry count and try again
                self._state_machine.fail_phase(next_phase_name, error_msg)
                # Reset to pending to retry
                phase_state = self._state_machine.state.phases.get(next_phase_name)
                if phase_state:
                    phase_state.status = PhaseStatus.PENDING
                    self._state_machine.save()
                continue

        # Check if all phases are complete
        if self._state_machine.is_complete():
            self._state_machine.set_status(PipelineStatus.COMPLETED)
            return True
        else:
            return False

    async def _run_phase(
        self,
        phase: Phase,
        input_data: Any,
        project_dir: Path,
        context: dict[str, Any],
    ) -> PhaseResult:
        """Run a single phase with error handling.

        Args:
            phase: Phase to run.
            input_data: Input data for the phase.
            project_dir: Project directory.
            context: Context dict.

        Returns:
            PhaseResult from the phase.
        """
        # Mark phase as running
        self._state_machine.start_phase(phase.name)

        try:
            # Validate input
            if not await phase.validate_input(input_data, context):
                return PhaseResult(
                    status=PhaseResultStatus.FAILED,
                    error="Input validation failed",
                )

            # Prepare
            prepared_context = await phase.prepare(input_data, project_dir, context)
            merged_context = {**context, **prepared_context}

            # Check if phase uses swarm pattern
            if phase.config.pattern == PlanningPattern.SWARM:
                result = await self._run_phase_with_swarm(
                    phase, input_data, project_dir, merged_context
                )
            else:
                # Run the phase normally
                result = await phase.run(input_data, project_dir, merged_context)

            # Record progress on success
            if result.is_success:
                self._error_recovery.record_progress()

            # Cleanup
            await phase.cleanup(result, project_dir)

            return result

        except Exception as e:
            return PhaseResult(
                status=PhaseResultStatus.FAILED,
                error=str(e),
            )

    async def _run_phase_with_swarm(
        self,
        phase: Phase,
        input_data: Any,
        project_dir: Path,
        context: dict[str, Any],
    ) -> PhaseResult:
        """Run a phase using swarm pattern (multiple parallel agents).

        Args:
            phase: Phase to run.
            input_data: Input data for the phase.
            project_dir: Project directory.
            context: Context dict.

        Returns:
            PhaseResult with aggregated output.
        """
        from agents.client import setup_project_settings

        print(f"\n[SWARM] Starting swarm execution for {phase.display_name}...")

        # Orchestrator responsibility: set up project settings ONCE before spawning agents
        # This prevents race conditions when multiple agents try to create settings simultaneously
        setup_project_settings(project_dir, verbose=False)

        # Get swarm configs based on phase type (pass context for rejection feedback)
        swarm_configs = self._get_swarm_configs(phase.name, input_data, context)

        if not swarm_configs:
            # Fallback to single agent execution
            print("[WARNING] No swarm configs available, falling back to single agent")
            return await phase.run(input_data, project_dir, context)

        print(f"   Running {len(swarm_configs)} agents in parallel...")

        # Progress callback
        def on_progress(agent_id: str, status: Any) -> None:
            print(f"   Agent {agent_id}: {status.value}")

        # Run swarm
        swarm_result = await self._swarm_controller.run_swarm(
            agents=swarm_configs,
            project_dir=project_dir,
            progress_callback=on_progress,
        )

        print(f"\n   Swarm completed: {swarm_result.success_count}/{len(swarm_configs)} succeeded")

        # Always log individual agent failures (even when swarm succeeds overall)
        for result in swarm_result.agent_results:
            if result.status == AgentStatus.FAILED:
                print(f"   [FAILED] Agent {result.agent_id} ({result.role}): {result.error}")

        # Check if enough agents succeeded
        if not swarm_result.any_succeeded:
            errors = [
                r.error for r in swarm_result.agent_results
                if r.error
            ]
            return PhaseResult(
                status=PhaseResultStatus.FAILED,
                error=f"All swarm agents failed: {'; '.join(errors[:3])}",
            )

        # Aggregate results
        print("   Aggregating results...")
        aggregator = create_aggregator(
            AggregationStrategy.CONCATENATE,
            include_role_headers=True,
        )
        aggregation_result = await aggregator.aggregate(swarm_result, context)

        # Save aggregated output
        output_file = project_dir / f"{phase.name}_output.md"
        output_file.write_text(aggregation_result.content, encoding="utf-8")
        print(f"   Output saved to {output_file}")

        return PhaseResult(
            status=PhaseResultStatus.NEEDS_APPROVAL if phase.config.checkpoint_pause else PhaseResultStatus.SUCCESS,
            output=aggregation_result.content,
            output_reference=str(output_file),
            metadata={
                "pattern": "swarm",
                "agent_count": len(swarm_configs),
                "success_count": swarm_result.success_count,
                "aggregation_strategy": aggregation_result.strategy_used.value,
            },
        )

    def _get_swarm_configs(
        self,
        phase_name: str,
        input_data: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> list[SwarmAgentConfig]:
        """Get swarm configurations for a phase.

        Args:
            phase_name: Name of the phase.
            input_data: Input data (idea or requirements).
            context: Optional context dict with rejection_feedback.

        Returns:
            List of SwarmAgentConfig objects.
        """
        # Extract rejection feedback if available
        rejection_feedback = context.get("rejection_feedback") if context else None

        if phase_name == "ideation":
            idea = str(input_data) if input_data else ""
            return create_ideation_swarm_configs(idea, rejection_feedback=rejection_feedback)

        elif phase_name == "architecture":
            requirements = str(input_data) if input_data else ""
            return create_architecture_swarm_configs(requirements)

        # Return empty list for phases without swarm support
        return []

    async def run_single_phase(
        self,
        phase_name: str,
        project_dir: Path,
        input_data: Optional[Any] = None,
    ) -> PhaseResult:
        """Run a single phase by name.

        Args:
            phase_name: Name of phase to run.
            project_dir: Project directory.
            input_data: Optional input data.

        Returns:
            PhaseResult from the phase.
        """
        phase = self._phases.get(phase_name)
        if phase is None:
            return PhaseResult(
                status=PhaseResultStatus.FAILED,
                error=f"Unknown phase: {phase_name}",
            )

        context: dict[str, Any] = {
            "project_dir": str(project_dir),
            "shutdown_handler": self._shutdown_handler,
            "error_recovery": self._error_recovery,
            "swarm_controller": self._swarm_controller,
        }

        return await self._run_phase(phase, input_data, project_dir, context)

    def get_phase(self, name: str) -> Optional[Phase]:
        """Get a registered phase by name.

        Args:
            name: Phase name.

        Returns:
            Phase or None if not found.
        """
        return self._phases.get(name)

    @property
    def registered_phases(self) -> list[str]:
        """Get list of registered phase names."""
        return list(self._phases.keys())


def create_default_runner(
    project_dir: Path,
    config: Optional[PhaseConfig] = None,
    include_planning_phases: bool = False,
    error_recovery_config: Optional[dict[str, Any]] = None,
    swarm_config: Optional[dict[str, Any]] = None,
) -> PhaseRunner:
    """Create a phase runner with default phases.

    Args:
        project_dir: Project directory.
        config: Optional phase config to use for all phases.
        include_planning_phases: If True, include ideation/architecture phases.
        error_recovery_config: Optional config for error recovery.
        swarm_config: Optional config for swarm controller with HTTP MCP servers.
            Example: {
                "max_concurrent": 3,
                "stagger_delay_seconds": 0.5,
                "mcp_servers": {"archon": {"type": "http", "url": "..."}},
                "mcp_tools": ["mcp__archon__search"]
            }

    Returns:
        Configured PhaseRunner.
    """
    from server.harness_agent.phases.implement import ImplementPhase
    from server.harness_agent.phases.initialize import InitializePhase

    # Determine phases to include
    if include_planning_phases:
        from server.harness_agent.phases.architecture import ArchitecturePhase
        from server.harness_agent.phases.ideation import IdeationPhase
        from server.harness_agent.phases.task_breakdown import TaskBreakdownPhase

        phase_names = [
            "ideation",
            "architecture",
            "task_breakdown",
            "initialize",
            "implement",
        ]
    else:
        phase_names = ["initialize", "implement"]

    # Create state machine
    state_machine = StateMachine(
        project_dir=project_dir,
        phases=phase_names,
    )

    # Create error recovery manager
    error_recovery = create_recovery_manager_from_config(error_recovery_config)

    # Create swarm controller with optional MCP config
    swarm_config = swarm_config or {}

    # Convert mcp_servers from config schema format to dict format
    mcp_servers_raw = swarm_config.get("mcp_servers", {})
    http_mcp_servers = {}
    for name, server_config in (mcp_servers_raw or {}).items():
        if hasattr(server_config, "model_dump"):
            # Pydantic model - convert to dict
            http_mcp_servers[name] = server_config.model_dump()
        else:
            http_mcp_servers[name] = server_config

    swarm_controller = SwarmController(
        max_concurrent=swarm_config.get("max_concurrent", 3),
        stagger_delay_seconds=swarm_config.get("stagger_delay_seconds", 1.0),
        http_mcp_servers=http_mcp_servers if http_mcp_servers else None,
        mcp_tools=swarm_config.get("mcp_tools"),
    )

    # Create runner
    runner = PhaseRunner(
        state_machine,
        error_recovery=error_recovery,
        swarm_controller=swarm_controller,
    )

    # Register phases
    if include_planning_phases:
        from server.harness_agent.phases.architecture import ArchitecturePhase
        from server.harness_agent.phases.ideation import IdeationPhase
        from server.harness_agent.phases.task_breakdown import TaskBreakdownPhase

        runner.register_phases([
            IdeationPhase(config),
            ArchitecturePhase(config),
            TaskBreakdownPhase(config),
            InitializePhase(config),
            ImplementPhase(config),
        ])
    else:
        runner.register_phases([
            InitializePhase(config),
            ImplementPhase(config),
        ])

    return runner
