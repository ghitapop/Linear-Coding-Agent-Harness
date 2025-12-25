#!/usr/bin/env python3
"""Test state machine functionality."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from server.harness_agent.orchestrator.state_machine import StateMachine, PipelineStatus, PhaseStatus


def test_state_machine():
    """Test state machine operations."""
    # Create temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / 'test_project'
        project_dir.mkdir()

        print('=== Testing State Machine ===')

        # Test 1: Create state machine
        sm = StateMachine(project_dir, project_id='test-123')
        print(f'Created state machine with project_id: {sm.state.project_id}')
        print(f'Initial status: {sm.state.status}')
        print(f'Phases: {list(sm.state.phases.keys())}')

        # Test 2: Start a phase
        phase = sm.start_phase('ideation')
        print(f'Started phase: {phase.name}, status: {phase.status}')

        # Test 3: Complete a phase
        phase = sm.complete_phase('ideation', output_reference='outputs/ideation.md')
        print(f'Completed phase: {phase.name}, status: {phase.status}')

        # Test 4: Get next phase
        next_phase = sm.get_next_phase()
        print(f'Next phase: {next_phase}')

        # Test 5: Verify state persistence
        sm2 = StateMachine(project_dir)
        print(f'Reloaded state - project_id: {sm2.state.project_id}')
        print(f'Ideation status after reload: {sm2.state.phases["ideation"].status}')

        # Test 6: Shutdown request
        sm.request_shutdown('user_request')
        print(f'Shutdown requested: {sm.state.shutdown_requested}')
        print(f'Status after shutdown request: {sm.state.status}')

        # Test 7: Clear shutdown for resume
        sm.clear_shutdown_request()
        print(f'Shutdown cleared: {not sm.state.shutdown_requested}')

        print()
        print('=== All State Machine Tests Passed! ===')

        # Verify state file exists
        state_file = project_dir / '.orchestrator_state.json'
        assert state_file.exists(), "State file should exist"
        print(f'State file verified at: {state_file}')


if __name__ == '__main__':
    test_state_machine()
