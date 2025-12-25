#!/usr/bin/env python3
"""Test script for CLI commands.

This script tests all the CLI commands to ensure they work correctly.
"""

import asyncio
import os
import json
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.cli_adapter import CLIAdapter
from orchestrator.project_registry import create_project_registry


async def test_commands():
    """Test all CLI commands."""
    print("=" * 60)
    print("Testing CLI Commands")
    print("=" * 60)

    # Setup
    workspace_dir = Path("./my_project")
    workspace_dir.mkdir(exist_ok=True)

    # Create a test project with state file
    test_project_dir = workspace_dir / "test_project"
    test_project_dir.mkdir(exist_ok=True)

    test_state = {
        "project_id": "test-123",
        "status": "paused",
        "current_phase": "ideation",
        "phases": {
            "ideation": {"name": "ideation", "status": "running"},
            "architecture": {"name": "architecture", "status": "pending"},
        },
        "heartbeat": "2025-12-25T10:00:00",
    }

    state_file = test_project_dir / ".orchestrator_state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(test_state, f)

    print(f"Created test project at: {test_project_dir}")
    print()

    # Create registry and adapter
    registry = create_project_registry(workspace_dir)
    adapter = CLIAdapter()

    # Get context
    context = registry.get_context()

    results = {}

    # Test 1: /help
    print("-" * 40)
    print("Test 1: /help command")
    print("-" * 40)
    result = adapter._show_help()
    print(result)
    results["help"] = "PASS" if "Available Commands" in result else "FAIL"
    print(f"Result: {results['help']}")
    print()

    # Test 2: /projects
    print("-" * 40)
    print("Test 2: /projects command")
    print("-" * 40)
    result = await adapter._handle_projects(context)
    print(result)
    results["projects"] = "PASS" if "test_project" in result else "FAIL"
    print(f"Result: {results['projects']}")
    print()

    # Test 3: /status (no arg - should show list)
    print("-" * 40)
    print("Test 3: /status command (no arg)")
    print("-" * 40)
    result = await adapter._handle_status([], context)
    print(result)
    results["status_no_arg"] = "PASS" if "test_project" in result else "FAIL"
    print(f"Result: {results['status_no_arg']}")
    print()

    # Test 4: /status test_project
    print("-" * 40)
    print("Test 4: /status test_project command")
    print("-" * 40)
    result = await adapter._handle_status(["test_project"], context)
    print(result)
    results["status_with_arg"] = "PASS" if "ideation" in result.lower() else "FAIL"
    print(f"Result: {results['status_with_arg']}")
    print()

    # Test 5: /resume (no arg - should show list)
    print("-" * 40)
    print("Test 5: /resume command (no arg)")
    print("-" * 40)
    result = await adapter._handle_resume([], context)
    print(result)
    results["resume_no_arg"] = "PASS" if "test_project" in result else "FAIL"
    print(f"Result: {results['resume_no_arg']}")
    print()

    # Test 6: /resume test_project
    print("-" * 40)
    print("Test 6: /resume test_project command")
    print("-" * 40)
    result = await adapter._handle_resume(["test_project"], context)
    print(result)
    results["resume_with_arg"] = "PASS" if "__RESUME__" in result else "FAIL"
    print(f"Result: {results['resume_with_arg']}")
    print()

    # Test 7: /new (check signal)
    print("-" * 40)
    print("Test 7: /new command")
    print("-" * 40)
    result = await adapter.handle_command("new", [], context)
    print(f"Result: {result}")
    results["new"] = "PASS" if result == "__NEW_PROJECT__" else "FAIL"
    print(f"Result: {results['new']}")
    print()

    # Test 8: /stop
    print("-" * 40)
    print("Test 8: /stop command")
    print("-" * 40)
    result = await adapter._handle_stop(context)
    print(f"Result: {result}")
    results["stop"] = "PASS" if "Stopping" in result else "FAIL"
    print(f"Result: {results['stop']}")
    print()

    # Test 9: /quit (check that it raises SystemExit)
    print("-" * 40)
    print("Test 9: /quit command")
    print("-" * 40)
    try:
        result = await adapter.handle_command("quit", [], context)
        results["quit"] = "FAIL"  # Should have raised SystemExit
    except SystemExit as e:
        print(f"SystemExit raised with code: {e.code}")
        results["quit"] = "PASS" if e.code == 0 else "FAIL"
    print(f"Result: {results['quit']}")
    print()

    # Test 10: /exit (check that it raises SystemExit)
    print("-" * 40)
    print("Test 10: /exit command")
    print("-" * 40)
    try:
        result = await adapter.handle_command("exit", [], context)
        results["exit"] = "FAIL"  # Should have raised SystemExit
    except SystemExit as e:
        print(f"SystemExit raised with code: {e.code}")
        results["exit"] = "PASS" if e.code == 0 else "FAIL"
    print(f"Result: {results['exit']}")
    print()

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v == "PASS")
    total = len(results)
    for test, result in results.items():
        status = "[OK]" if result == "PASS" else "[FAIL]"
        print(f"  {status} {test}: {result}")
    print()
    print(f"Passed: {passed}/{total}")

    # Cleanup
    if state_file.exists():
        state_file.unlink()
    if test_project_dir.exists():
        test_project_dir.rmdir()

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(test_commands())
    sys.exit(0 if success else 1)
