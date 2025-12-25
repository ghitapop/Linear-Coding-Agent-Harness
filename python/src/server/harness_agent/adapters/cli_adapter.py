"""CLI adapter for interactive command line interface."""

import asyncio
import sys
from typing import Any, Callable, Coroutine, Optional

from server.harness_agent.adapters.base import InputAdapter
from server.harness_agent.orchestrator.state_machine import PhaseStatus, PipelineState, PipelineStatus


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


def colorize(text: str, *codes: str) -> str:
    """Apply color codes to text.

    Args:
        text: Text to colorize.
        *codes: Color codes to apply.

    Returns:
        Colorized text string.
    """
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + Colors.RESET


class CLIAdapter(InputAdapter):
    """Interactive CLI adapter with slash commands.

    Supports commands:
    - /projects - List all projects
    - /status [id] - Show project status
    - /resume <id> - Resume a paused project
    - /stop - Stop current project
    - /help - Show available commands
    """

    BANNER = """
+---------------------------------------------------------------+
|           Autonomous Orchestrator Framework v1.0               |
+---------------------------------------------------------------+
"""

    COMMANDS = {
        "projects": "List all projects",
        "status": "Show project status [id]",
        "resume": "Resume a paused project <id>",
        "stop": "Stop current project gracefully",
        "new": "Start a new project (abandons current)",
        "quit": "Exit the application",
        "exit": "Exit the application",
        "help": "Show this help message",
    }

    def __init__(
        self,
        on_command: Optional[Callable[[str, list[str]], Coroutine[Any, Any, Optional[str]]]] = None,
    ) -> None:
        """Initialize the CLI adapter.

        Args:
            on_command: Optional callback for handling commands.
        """
        self._on_command = on_command
        self._running = False
        self._current_project_id: Optional[str] = None

    async def start(self) -> None:
        """Start the CLI adapter."""
        self._running = True
        print(colorize(self.BANNER, Colors.CYAN, Colors.BOLD))
        print("Type what you want to build, or use /help for commands.")
        print(colorize("Press ESC or CTRL+C to interrupt running operations. Use /quit to exit.\n", Colors.DIM))

    async def stop(self) -> None:
        """Stop the CLI adapter."""
        self._running = False
        print("\nGoodbye!")

    async def get_initial_idea(self) -> str:
        """Get the initial project idea from user."""
        print(colorize("What would you like to build?", Colors.BOLD))
        return await self._read_input("> ")

    async def get_project_name(self, suggested_name: Optional[str] = None) -> str:
        """Get the project name from user."""
        prompt = "Project name"
        if suggested_name:
            prompt += f" [{suggested_name}]"
        prompt += ": "

        name = await self._read_input(prompt)
        return name if name else (suggested_name or "project")

    async def get_approval(
        self,
        summary: str,
        phase: str,
        options: Optional[list[str]] = None,
    ) -> tuple[bool, Optional[str]]:
        """Get user approval at checkpoints.

        Returns:
            Tuple of (approved: bool, feedback: Optional[str]).
            feedback is only set when user rejects and provides a reason.
        """
        options = options or ["Y", "n", "view"]

        print()
        print(colorize(f"=== {phase.upper()} CHECKPOINT ===", Colors.YELLOW, Colors.BOLD))
        print()
        print(summary)
        print()

        options_str = "/".join(options)
        response = await self._read_input(f"Approve? [{options_str}]: ")
        response = response.lower().strip()

        if response in ["y", "yes", ""]:
            return (True, None)
        elif response == "view":
            # Show more details - this could be enhanced
            print("(No additional details available)")
            return await self.get_approval(summary, phase, options)
        else:
            # Ask for feedback on why they rejected
            print()
            print(colorize("Why did you reject this plan?", Colors.CYAN))
            print(colorize("(Your feedback will be incorporated when retrying. Press Enter to skip)", Colors.DIM))
            feedback = await self._read_input("> ")
            feedback = feedback.strip() if feedback else None
            return (False, feedback)

    async def get_clarification(self, question: str) -> str:
        """Ask user for clarification."""
        print()
        print(colorize("Question:", Colors.CYAN))
        print(question)
        return await self._read_input("> ")

    async def show_progress(self, state: PipelineState) -> None:
        """Display current progress to user."""
        print()
        print(colorize("=== PROGRESS ===", Colors.BOLD))
        print(f"Project: {state.project_id}")
        print(f"Status: {self._format_status(state.status)}")

        if state.current_phase:
            print(f"Current Phase: {state.current_phase}")

        print()
        print("Phases:")
        for name, phase in state.phases.items():
            status_icon = self._get_status_icon(phase.status)
            print(f"  {status_icon} {name}: {phase.status.value}")

        print()

    async def show_message(
        self,
        message: str,
        level: str = "info",
    ) -> None:
        """Show a message to the user."""
        if level == "error":
            print(colorize(f"ERROR: {message}", Colors.RED))
        elif level == "warning":
            print(colorize(f"WARNING: {message}", Colors.YELLOW))
        elif level == "success":
            print(colorize(f"SUCCESS: {message}", Colors.GREEN))
        else:
            print(message)

    async def show_error(
        self,
        error: str,
        options: Optional[list[str]] = None,
    ) -> str:
        """Show error and get user decision."""
        options = options or ["retry", "skip", "abort"]

        print()
        print(colorize("=== ERROR ===", Colors.RED, Colors.BOLD))
        print(error)
        print()

        options_str = "/".join(options)
        response = await self._read_input(f"What would you like to do? [{options_str}]: ")
        response = response.lower().strip()

        if response in options or response == "":
            return response if response else options[0]
        else:
            print(f"Invalid option. Choose from: {options_str}")
            return await self.show_error(error, options)

    async def get_command(self) -> tuple[str, list[str]]:
        """Get the next command from user."""
        line = await self._read_input("> ")
        line = line.strip()

        if line.startswith("/"):
            parts = line[1:].split()
            command = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []
            return (command, args)
        else:
            return ("", [line] if line else [])

    async def handle_command(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> Optional[str]:
        """Handle a slash command.

        Args:
            command: The command name (without slash).
            args: Command arguments.
            context: Context dict with orchestrator state.

        Returns:
            Optional response message, or raises SystemExit for quit.
        """
        if command == "help":
            return self._show_help()
        elif command == "projects":
            return await self._handle_projects(context)
        elif command == "status":
            return await self._handle_status(args, context)
        elif command == "resume":
            return await self._handle_resume(args, context)
        elif command == "stop":
            return await self._handle_stop(context)
        elif command == "new":
            return "__NEW_PROJECT__"  # Special signal to start new project
        elif command in ("quit", "exit"):
            return await self._handle_quit()
        else:
            return f"Unknown command: /{command}. Type /help for available commands."

    def _show_help(self) -> str:
        """Show help message."""
        lines = [
            colorize("Available Commands:", Colors.BOLD),
            "",
        ]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"  /{cmd:10} - {desc}")
        lines.append("")
        lines.append(colorize("Keyboard Shortcuts:", Colors.BOLD))
        lines.append("  ESC         - Interrupt current operation and return to prompt")
        lines.append("  CTRL+C      - Same as ESC (interrupt, not exit)")
        lines.append("  Enter       - Continue current project (after interrupt)")
        lines.append("")
        lines.append("Type what you want to build to start a new project.")
        lines.append("After interrupting, press Enter to continue or /new to start fresh.")
        return "\n".join(lines)

    async def _handle_projects(self, context: dict[str, Any]) -> str:
        """Handle /projects command."""
        projects = context.get("projects", [])

        if not projects:
            return "No projects found. Type what you want to build to start a new project."

        lines = [
            colorize("Your Projects:", Colors.BOLD),
            "",
            f"{'ID':<8} {'Name':<20} {'Status':<12} {'Phase':<15} {'Progress'}",
            "-" * 70,
        ]

        for project in projects:
            progress = project.get("progress", "0/0")
            lines.append(
                f"{project['id']:<8} {project['name']:<20} "
                f"{project['status']:<12} {project.get('phase', '-'):<15} {progress}"
            )

        return "\n".join(lines)

    async def _handle_status(self, args: list[str], context: dict[str, Any]) -> str:
        """Handle /status command."""
        project_id = args[0] if args else context.get("current_project_id")

        if not project_id:
            # If no current project and no arg, show list of projects
            projects = context.get("projects", [])
            if not projects:
                return "No projects found. Type what you want to build to start a new project."

            lines = ["Usage: /status <project_id>", "", "Available projects:"]
            for p in projects:
                lines.append(f"  {p['name']}: {p['status']} (phase: {p.get('phase', '-')})")
            return "\n".join(lines)

        project = context.get("projects_by_id", {}).get(project_id)
        if not project:
            return f"Project not found: {project_id}"

        # Handle status string that might not be a valid PipelineStatus
        status_str = project.get('status', 'unknown')
        try:
            status_formatted = self._format_status(PipelineStatus(status_str))
        except ValueError:
            status_formatted = status_str

        lines = [
            colorize(f"Project: {project['name']}", Colors.BOLD),
            f"  ID: {project['id']}",
            f"  Directory: {project.get('dir', '-')}",
            f"  Status: {status_formatted}",
            f"  Phase: {project.get('phase', '-')}",
            f"  Progress: {project.get('progress', '0/0')}",
            f"  Last Activity: {project.get('last_activity', 'Unknown')}",
        ]

        # Show phase details if available
        phases = project.get('phases', {})
        if phases:
            lines.append("")
            lines.append(colorize("  Phases:", Colors.BOLD))
            for name, phase_data in phases.items():
                phase_status = phase_data.get('status', 'pending')
                icon = self._get_status_icon(PhaseStatus(phase_status)) if phase_status in ['pending', 'running', 'completed', 'failed', 'skipped'] else "[?]"
                lines.append(f"    {icon} {name}: {phase_status}")

        return "\n".join(lines)

    async def _handle_resume(self, args: list[str], context: dict[str, Any]) -> str:
        """Handle /resume command."""
        if not args:
            # If no arg, show available projects
            projects = context.get("projects", [])
            paused_projects = [p for p in projects if p.get("status") in ["paused", "stopping", "running"]]

            if not paused_projects:
                return "No resumable projects found. Use /projects to list all projects."

            lines = ["Usage: /resume <project_id>", "", "Resumable projects:"]
            for p in paused_projects:
                lines.append(f"  {p['name']}: {p['status']} (phase: {p.get('phase', '-')})")
            return "\n".join(lines)

        project_id = args[0]

        # Check if project exists
        project = context.get("projects_by_id", {}).get(project_id)
        if not project:
            return f"Project not found: {project_id}"

        # Return special signal to resume
        return f"__RESUME__{project_id}"

    async def _handle_stop(self, context: dict[str, Any]) -> str:
        """Handle /stop command."""
        # Delegate to orchestrator via callback
        if self._on_command:
            result = await self._on_command("stop", [])
            return result or "Stopping current project..."
        return "Stopping current project..."

    async def _handle_quit(self) -> str:
        """Handle /quit or /exit command."""
        from server.harness_agent.orchestrator.keyboard_handler import get_keyboard_handler
        handler = get_keyboard_handler()
        handler.request_quit()
        raise SystemExit(0)

    async def _read_input(self, prompt: str) -> str:
        """Read input from user asynchronously.

        Args:
            prompt: The prompt to display.

        Returns:
            The user's input.
        """
        from server.harness_agent.orchestrator.keyboard_handler import pause_keyboard, resume_keyboard

        # Pause keyboard handler so it doesn't consume input
        pause_keyboard()

        try:
            # For Windows compatibility, use synchronous input in thread
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: input(prompt))
        finally:
            # Resume keyboard handler for agent operations
            resume_keyboard()

    def _format_status(self, status: PipelineStatus) -> str:
        """Format pipeline status with color."""
        status_colors = {
            PipelineStatus.NOT_STARTED: Colors.DIM,
            PipelineStatus.RUNNING: Colors.GREEN,
            PipelineStatus.PAUSED: Colors.YELLOW,
            PipelineStatus.STOPPING: Colors.YELLOW,
            PipelineStatus.STOPPED: Colors.DIM,
            PipelineStatus.COMPLETED: Colors.GREEN,
            PipelineStatus.FAILED: Colors.RED,
        }
        color = status_colors.get(status, Colors.WHITE)
        return colorize(status.value, color)

    def _get_status_icon(self, status: PhaseStatus) -> str:
        """Get status icon for phase."""
        icons = {
            PhaseStatus.PENDING: "[ ]",
            PhaseStatus.RUNNING: colorize("[*]", Colors.BLUE),
            PhaseStatus.COMPLETED: colorize("[+]", Colors.GREEN),
            PhaseStatus.FAILED: colorize("[x]", Colors.RED),
            PhaseStatus.SKIPPED: colorize("[-]", Colors.DIM),
        }
        return icons.get(status, "[?]")


def create_cli_adapter() -> CLIAdapter:
    """Create a CLI adapter instance.

    Returns:
        Configured CLIAdapter.
    """
    return CLIAdapter()
