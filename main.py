#!/usr/bin/env python3
"""Main entry point for the Autonomous Orchestrator Framework.

Usage:
    # Interactive CLI mode (default)
    python main.py

    # With config file
    python main.py --config orchestrator.yaml

    # Resume paused project
    python main.py --resume

    # Check status
    python main.py --status

    # API server mode (Docker)
    python main.py --api --port 8080

    # Non-interactive mode with idea file
    python main.py --idea-file idea.md --no-interactive

    # Stop a running project (from another terminal)
    python main.py --stop
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Autonomous Orchestrator Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--api",
        action="store_true",
        help="Run in API server mode (for Docker deployment)",
    )
    mode_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume a paused project",
    )
    mode_group.add_argument(
        "--status",
        action="store_true",
        help="Show current project status",
    )
    mode_group.add_argument(
        "--stop",
        action="store_true",
        help="Stop a running project gracefully",
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("orchestrator.yaml"),
        help="Path to configuration file (default: orchestrator.yaml)",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory (overrides config)",
    )

    # API mode options
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for API server (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for API server (default: 0.0.0.0)",
    )

    # Non-interactive options
    parser.add_argument(
        "--idea-file",
        type=Path,
        default=None,
        help="File containing project idea (for non-interactive mode)",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Run in non-interactive mode (auto-approve checkpoints)",
    )

    # Agent options
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (overrides config)",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help="Maximum number of agent sessions (overrides config)",
    )

    return parser.parse_args()


async def run_cli_mode(args: argparse.Namespace) -> int:
    """Run in interactive CLI mode.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from adapters.cli_adapter import CLIAdapter, create_cli_adapter
    from config.loader import load_config, create_default_config
    from orchestrator.phase_runner import create_default_runner
    from orchestrator.shutdown import create_shutdown_handler
    from orchestrator.heartbeat import create_heartbeat_manager

    # Load config
    config = None
    if args.config.exists():
        try:
            config = load_config(args.config)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

    # Determine project directory
    if args.project_dir:
        project_dir = args.project_dir
    elif config:
        project_dir = config.project.directory
    else:
        project_dir = Path("./my_project")

    project_dir = project_dir.resolve()

    # Create CLI adapter
    adapter = create_cli_adapter()

    # Start adapter
    await adapter.start()

    try:
        # Get initial idea if starting new project
        idea = None
        if args.idea_file:
            idea = args.idea_file.read_text()
        elif not args.resume:
            idea = await adapter.get_initial_idea()
            if not idea:
                print("No idea provided. Exiting.")
                return 0

        # Get project name
        if idea and not args.resume:
            suggested_name = idea.split()[0].lower()[:20] if idea else "project"
            project_name = await adapter.get_project_name(suggested_name)
            project_dir = project_dir.parent / project_name

        # Create project directory
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create phase runner
        runner = create_default_runner(project_dir)

        # Create shutdown handler
        shutdown_handler = create_shutdown_handler(runner._state_machine)

        # Install signal handlers
        try:
            shutdown_handler.install_handlers()
        except RuntimeError:
            pass

        # Create heartbeat manager
        heartbeat = create_heartbeat_manager(runner._state_machine)

        # Run with heartbeat
        async with heartbeat:
            # Define approval callback
            async def approval_callback(summary: str, phase: str) -> bool:
                if args.no_interactive:
                    return True
                return await adapter.get_approval(summary, phase)

            # Run phases
            success = await runner.run_until_complete(
                project_dir=project_dir,
                input_data={"idea": idea} if idea else None,
                approval_callback=approval_callback,
            )

            if success:
                await adapter.show_message("All phases completed successfully!", level="success")
            else:
                await adapter.show_message("Pipeline stopped or failed.", level="warning")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    finally:
        await adapter.stop()


async def run_api_mode(args: argparse.Namespace) -> int:
    """Run in API server mode.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    import uvicorn
    from api.main import create_app

    # Create app
    app = create_app()

    # Configure uvicorn
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Run server
    await server.serve()

    return 0


async def show_status(args: argparse.Namespace) -> int:
    """Show current project status.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from config.loader import load_config
    from orchestrator.state_machine import StateMachine
    from orchestrator.resume import ResumeManager

    # Determine project directory
    if args.project_dir:
        project_dir = args.project_dir
    elif args.config.exists():
        config = load_config(args.config)
        project_dir = config.project.directory
    else:
        project_dir = Path("./my_project")

    project_dir = project_dir.resolve()

    # Check if state file exists
    state_file = project_dir / ".orchestrator_state.json"
    if not state_file.exists():
        print(f"No orchestrator state found in {project_dir}")
        return 1

    # Load state machine
    state_machine = StateMachine(project_dir)
    resume_manager = ResumeManager(state_machine)

    # Get summary
    summary = resume_manager.get_status_summary()

    # Display status
    print()
    print(f"Project: {summary['project_id']}")
    print(f"Status: {summary['status']}")
    print(f"Current Phase: {summary['current_phase'] or '-'}")
    print()
    print("Phases:")
    for status, count in summary['phases'].items():
        if count > 0:
            print(f"  {status}: {count}")
    print()
    if summary['last_checkpoint']:
        print(f"Last Checkpoint: {summary['last_checkpoint']}")
    if summary['shutdown_requested']:
        print(f"Shutdown Requested: {summary['shutdown_reason']}")
    if summary['interrupted_items'] > 0:
        print(f"Interrupted Items: {summary['interrupted_items']}")
    if summary['is_crash_recovery']:
        print("WARNING: Previous run may have crashed")
    print()

    return 0


async def resume_project(args: argparse.Namespace) -> int:
    """Resume a paused project.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from config.loader import load_config
    from orchestrator.state_machine import StateMachine
    from orchestrator.resume import ResumeManager
    from orchestrator.phase_runner import PhaseRunner
    from orchestrator.shutdown import create_shutdown_handler
    from orchestrator.heartbeat import create_heartbeat_manager
    from phases.initialize import InitializePhase
    from phases.implement import ImplementPhase
    from adapters.cli_adapter import create_cli_adapter

    # Determine project directory
    if args.project_dir:
        project_dir = args.project_dir
    elif args.config.exists():
        config = load_config(args.config)
        project_dir = config.project.directory
    else:
        project_dir = Path("./my_project")

    project_dir = project_dir.resolve()

    # Check if state file exists
    state_file = project_dir / ".orchestrator_state.json"
    if not state_file.exists():
        print(f"No orchestrator state found in {project_dir}")
        return 1

    # Load state machine
    state_machine = StateMachine(project_dir)
    resume_manager = ResumeManager(state_machine)

    # Check if can resume
    if not resume_manager.can_resume():
        print("Project cannot be resumed (not in resumable state)")
        return 1

    # Prepare for resume
    resume_point = resume_manager.prepare_for_resume()

    print(f"Resuming from phase: {resume_point.phase}")
    if resume_point.is_crash_recovery:
        print("Note: Recovering from crash")
    if resume_point.work_items_to_retry:
        print(f"Will retry {len(resume_point.work_items_to_retry)} work items")

    # Create components
    shutdown_handler = create_shutdown_handler(state_machine)
    try:
        shutdown_handler.install_handlers()
    except RuntimeError:
        pass

    runner = PhaseRunner(state_machine, shutdown_handler)
    runner.register_phases([
        InitializePhase(),
        ImplementPhase(),
    ])

    heartbeat = create_heartbeat_manager(state_machine)
    adapter = create_cli_adapter()

    await adapter.start()

    try:
        async with heartbeat:
            async def approval_callback(summary: str, phase: str) -> bool:
                if args.no_interactive:
                    return True
                return await adapter.get_approval(summary, phase)

            success = await runner.run_until_complete(
                project_dir=project_dir,
                approval_callback=approval_callback,
            )

            if success:
                await adapter.show_message("All phases completed successfully!", level="success")
            else:
                await adapter.show_message("Pipeline stopped or failed.", level="warning")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    finally:
        await adapter.stop()


async def stop_project(args: argparse.Namespace) -> int:
    """Stop a running project.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from config.loader import load_config
    from orchestrator.state_machine import StateMachine, PipelineStatus

    # Determine project directory
    if args.project_dir:
        project_dir = args.project_dir
    elif args.config.exists():
        config = load_config(args.config)
        project_dir = config.project.directory
    else:
        project_dir = Path("./my_project")

    project_dir = project_dir.resolve()

    # Check if state file exists
    state_file = project_dir / ".orchestrator_state.json"
    if not state_file.exists():
        print(f"No orchestrator state found in {project_dir}")
        return 1

    # Load state machine and request shutdown
    state_machine = StateMachine(project_dir)
    state_machine.request_shutdown("user_request")

    print(f"Shutdown requested for project in {project_dir}")
    print("The running orchestrator will stop at the next safe point.")

    return 0


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Route to appropriate mode
    if args.api:
        return await run_api_mode(args)
    elif args.status:
        return await show_status(args)
    elif args.resume:
        return await resume_project(args)
    elif args.stop:
        return await stop_project(args)
    else:
        return await run_cli_mode(args)


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
