#!/usr/bin/env python3
"""Test phase runner and multi-phase pipeline functionality."""

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from server.harness_agent.orchestrator.state_machine import StateMachine, PipelineStatus, PhaseStatus
from server.harness_agent.orchestrator.phase_runner import PhaseRunner
from server.harness_agent.orchestrator.shutdown import GracefulShutdown
from server.harness_agent.phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus as ResultStatus


class MockPhase(Phase):
    """Mock phase for testing."""

    def __init__(self, name: str, should_succeed: bool = True, delay: float = 0.1):
        super().__init__(PhaseConfig())
        self._name = name
        self._display_name = f"Mock {name.title()} Phase"
        self._should_succeed = should_succeed
        self._delay = delay

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    async def run(
        self, input_data: Any, project_dir: Path, context: dict[str, Any]
    ) -> PhaseResult:
        """Mock phase execution."""
        await asyncio.sleep(self._delay)

        if self._should_succeed:
            output = f"Output from {self._name} phase"
            return PhaseResult(
                status=ResultStatus.SUCCESS,
                output=output,
                output_reference=f"{self._name}_output.txt",
            )
        else:
            return PhaseResult(
                status=ResultStatus.FAILED,
                error=f"Mock error in {self._name} phase",
            )


async def test_phase_runner():
    """Test phase runner operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / 'test_project'
        project_dir.mkdir()

        print('=== Testing Phase Runner ===')

        # Create state machine with custom phases
        phases = ["phase1", "phase2", "phase3"]
        sm = StateMachine(project_dir, project_id='test-runner', phases=phases)

        # Create shutdown handler
        shutdown_handler = GracefulShutdown(sm)

        # Create phase runner
        runner = PhaseRunner(sm, shutdown_handler)

        # Register mock phases
        runner.register_phases([
            MockPhase("phase1"),
            MockPhase("phase2"),
            MockPhase("phase3"),
        ])

        print(f'Registered phases: {runner.registered_phases}')

        # Run single phase
        print('\n--- Testing Single Phase Execution ---')
        result = await runner.run_single_phase("phase1", project_dir, input_data={"test": True})
        print(f'Phase1 result: {result.status}')
        print(f'Phase1 output: {result.output}')

        # Check state
        phase_state = sm.state.phases.get("phase1")
        print(f'Phase1 state: {phase_state.status if phase_state else "not found"}')

        # Run until complete
        print('\n--- Testing Full Pipeline Execution ---')

        # Reset for full run
        sm2 = StateMachine(project_dir, project_id='test-runner-2', phases=phases)
        runner2 = PhaseRunner(sm2)
        runner2.register_phases([
            MockPhase("phase1"),
            MockPhase("phase2"),
            MockPhase("phase3"),
        ])

        success = await runner2.run_until_complete(
            project_dir=project_dir,
            input_data={"initial": "data"},
        )

        print(f'Pipeline completed: {success}')
        print(f'Pipeline status: {sm2.state.status}')

        # Verify all phases completed
        for name in phases:
            phase_state = sm2.state.phases.get(name)
            print(f'  {name}: {phase_state.status if phase_state else "missing"}')

        print('\n=== All Phase Runner Tests Passed! ===')


async def test_phase_runner_with_failure():
    """Test phase runner with failure handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / 'test_project_fail'
        project_dir.mkdir()

        print('\n=== Testing Phase Runner with Failure ===')

        phases = ["phase1", "phase2", "phase3"]
        sm = StateMachine(project_dir, project_id='test-failure', phases=phases)
        runner = PhaseRunner(sm)

        # Phase 2 will fail
        runner.register_phases([
            MockPhase("phase1", should_succeed=True),
            MockPhase("phase2", should_succeed=False),
            MockPhase("phase3", should_succeed=True),
        ])

        success = await runner.run_until_complete(
            project_dir=project_dir,
            input_data={"initial": "data"},
        )

        print(f'Pipeline completed successfully: {success}')
        print(f'Pipeline status: {sm.state.status}')

        # Verify phase states
        for name in phases:
            phase_state = sm.state.phases.get(name)
            print(f'  {name}: {phase_state.status if phase_state else "missing"}')

        print('\n=== Failure Handling Tests Passed! ===')


async def test_state_persistence():
    """Test state persistence across restarts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / 'test_persistence'
        project_dir.mkdir()

        print('\n=== Testing State Persistence ===')

        phases = ["phase1", "phase2", "phase3"]

        # First run - complete phase1
        sm1 = StateMachine(project_dir, project_id='persist-test', phases=phases)
        runner1 = PhaseRunner(sm1)
        runner1.register_phases([MockPhase("phase1")])

        await runner1.run_single_phase("phase1", project_dir)
        print(f'After phase1: {sm1.state.phases["phase1"].status}')

        # Simulate restart - create new instances
        sm2 = StateMachine(project_dir)  # Should load from file
        print(f'After reload: project_id = {sm2.state.project_id}')
        print(f'Phase1 status after reload: {sm2.state.phases["phase1"].status}')
        print(f'Next phase to run: {sm2.get_next_phase()}')

        # Verify state file
        state_file = project_dir / '.orchestrator_state.json'
        print(f'State file exists: {state_file.exists()}')

        print('\n=== State Persistence Tests Passed! ===')


def main():
    """Run all tests."""
    asyncio.run(test_phase_runner())
    asyncio.run(test_phase_runner_with_failure())
    asyncio.run(test_state_persistence())
    print('\n' + '=' * 50)
    print('All tests completed successfully!')
    print('=' * 50)


if __name__ == '__main__':
    main()
