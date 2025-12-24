"""Work tracker backends for the Autonomous Orchestrator Framework.

This package provides pluggable backends for tracking work items:
- PostgresBackend: PostgreSQL database backend (default)
- JSONBackend: Local JSON file backend (for development/testing)
- LinearBackend: Linear.app integration backend

Usage:
    from backends import create_backend, WorkTracker
    from config.schema import BackendType

    # Create a backend from config
    backend = create_backend(BackendType.POSTGRES, database_url="...")

    # Or create specific backends
    from backends.json_backend import JSONBackend
    backend = JSONBackend(project_dir)
"""

from backends.base import (
    WorkItem,
    WorkItemCreate,
    WorkItemStatus,
    WorkItemUpdate,
    WorkTracker,
)
from backends.json_backend import JSONBackend
from backends.linear_backend import LinearBackend
from backends.postgres_backend import PostgresBackend

__all__ = [
    # Base classes
    "WorkTracker",
    "WorkItem",
    "WorkItemCreate",
    "WorkItemUpdate",
    "WorkItemStatus",
    # Backends
    "JSONBackend",
    "LinearBackend",
    "PostgresBackend",
    # Factory
    "create_backend",
]


def create_backend(
    backend_type: str,
    project_dir: str | None = None,
    database_url: str | None = None,
    linear_api_key: str | None = None,
    json_file_path: str | None = None,
) -> WorkTracker:
    """Create a work tracker backend from configuration.

    Args:
        backend_type: Backend type ("postgres", "json", "linear").
        project_dir: Project directory path.
        database_url: PostgreSQL connection URL (for postgres backend).
        linear_api_key: Linear API key (for linear backend).
        json_file_path: Path to JSON file (for json backend).

    Returns:
        Configured WorkTracker instance.

    Raises:
        ValueError: If backend type is not supported.
    """
    from pathlib import Path

    if backend_type == "postgres":
        return PostgresBackend(database_url=database_url)
    elif backend_type == "json":
        if json_file_path:
            path = Path(json_file_path)
        elif project_dir:
            path = Path(project_dir) / ".work_items.json"
        else:
            path = Path(".work_items.json")
        return JSONBackend(file_path=path)
    elif backend_type == "linear":
        return LinearBackend(api_key=linear_api_key)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")
