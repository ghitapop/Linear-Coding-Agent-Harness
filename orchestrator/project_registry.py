"""Project registry for tracking projects in the workspace.

Scans workspace directories for .orchestrator_state.json files and provides
project listing, status queries, and resume capabilities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class ProjectRegistry:
    """Registry for managing projects in a workspace.

    Scans workspace directories for projects with orchestrator state files
    and provides project discovery, status queries, and resume support.
    """

    STATE_FILENAME = ".orchestrator_state.json"

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the project registry.

        Args:
            workspace_dir: Root workspace directory containing projects.
        """
        self._workspace_dir = workspace_dir
        self._current_project_id: Optional[str] = None

    @property
    def workspace_dir(self) -> Path:
        """Get the workspace directory."""
        return self._workspace_dir

    @property
    def current_project_id(self) -> Optional[str]:
        """Get the current project ID."""
        return self._current_project_id

    @current_project_id.setter
    def current_project_id(self, value: Optional[str]) -> None:
        """Set the current project ID."""
        self._current_project_id = value

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects in the workspace.

        Returns:
            List of project info dicts with id, name, status, phase, progress.
        """
        projects = []

        if not self._workspace_dir.exists():
            return projects

        # Scan all subdirectories for state files
        for project_dir in self._workspace_dir.iterdir():
            if not project_dir.is_dir():
                continue

            state_file = project_dir / self.STATE_FILENAME
            if not state_file.exists():
                continue

            try:
                project_info = self._load_project_info(project_dir, state_file)
                if project_info:
                    projects.append(project_info)
            except (json.JSONDecodeError, KeyError, IOError):
                # Skip corrupted state files
                continue

        # Sort by last activity (most recent first)
        projects.sort(key=lambda p: p.get("last_activity_ts", 0), reverse=True)

        return projects

    def get_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get a specific project by ID.

        Args:
            project_id: The project identifier.

        Returns:
            Project info dict or None if not found.
        """
        projects = self.list_projects()
        for project in projects:
            if project["id"] == project_id or project["name"] == project_id:
                return project
        return None

    def get_project_dir(self, project_id: str) -> Optional[Path]:
        """Get the directory for a project.

        Args:
            project_id: The project identifier.

        Returns:
            Project directory path or None if not found.
        """
        if not self._workspace_dir.exists():
            return None

        for project_dir in self._workspace_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # Check if directory name matches
            if project_dir.name == project_id:
                return project_dir

            # Check state file for matching project_id
            state_file = project_dir / self.STATE_FILENAME
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    if state.get("project_id") == project_id:
                        return project_dir
                except (json.JSONDecodeError, IOError):
                    continue

        return None

    def get_context(self) -> dict[str, Any]:
        """Get context dict for CLI adapter.

        Returns:
            Context dict with projects, projects_by_id, current_project_id.
        """
        projects = self.list_projects()
        projects_by_id = {p["id"]: p for p in projects}

        # Also index by name for convenience
        for p in projects:
            projects_by_id[p["name"]] = p

        return {
            "projects": projects,
            "projects_by_id": projects_by_id,
            "current_project_id": self._current_project_id,
        }

    def _load_project_info(
        self,
        project_dir: Path,
        state_file: Path,
    ) -> Optional[dict[str, Any]]:
        """Load project info from state file.

        Args:
            project_dir: Project directory.
            state_file: Path to state file.

        Returns:
            Project info dict or None if invalid.
        """
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        project_id = state.get("project_id", project_dir.name)
        status = state.get("status", "unknown")
        current_phase = state.get("current_phase", "-")
        phases = state.get("phases", {})

        # Calculate progress
        total_phases = len(phases)
        completed_phases = sum(
            1 for p in phases.values()
            if p.get("status") in ["completed", "skipped"]
        )
        progress = f"{completed_phases}/{total_phases}"

        # Get last activity timestamp
        heartbeat = state.get("heartbeat")
        last_checkpoint = state.get("last_checkpoint")
        last_activity = heartbeat or last_checkpoint or None
        last_activity_ts = 0

        if last_activity:
            try:
                dt = datetime.fromisoformat(last_activity)
                last_activity_ts = dt.timestamp()
                last_activity = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                last_activity = "Unknown"

        return {
            "id": project_id,
            "name": project_dir.name,
            "dir": str(project_dir),
            "status": status,
            "phase": current_phase or "-",
            "progress": progress,
            "last_activity": last_activity or "Unknown",
            "last_activity_ts": last_activity_ts,
            "phases": phases,
            "shutdown_requested": state.get("shutdown_requested", False),
        }


def create_project_registry(workspace_dir: Path) -> ProjectRegistry:
    """Create a project registry for a workspace.

    Args:
        workspace_dir: Root workspace directory.

    Returns:
        Configured ProjectRegistry.
    """
    return ProjectRegistry(workspace_dir)
