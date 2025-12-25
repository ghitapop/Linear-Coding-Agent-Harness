"""Abstract base classes for work tracker backends.

This module defines the abstract interface that all work tracker backends
must implement. This allows the orchestrator to work with different backends
(PostgreSQL, JSON files, Linear.app) through a unified interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence


class WorkItemStatus(str, Enum):
    """Work item status values."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class WorkItemPriority(int, Enum):
    """Work item priority levels (Linear-compatible)."""

    URGENT = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    NO_PRIORITY = 0


@dataclass
class WorkItem:
    """Represents a work item (task/feature) to be implemented.

    This is a backend-agnostic representation of a work item that can be
    serialized to/from different storage backends.
    """

    id: str
    project_id: str
    title: str
    description: Optional[str] = None
    status: WorkItemStatus = WorkItemStatus.TODO
    priority: int = WorkItemPriority.MEDIUM
    phase: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    external_id: Optional[str] = None  # ID in external system (e.g., Linear)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "phase": self.phase,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies,
            "labels": self.labels,
            "metadata": self.metadata,
            "external_id": self.external_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            title=data["title"],
            description=data.get("description"),
            status=WorkItemStatus(data.get("status", "todo")),
            priority=data.get("priority", WorkItemPriority.MEDIUM),
            phase=data.get("phase"),
            parent_id=data.get("parent_id"),
            dependencies=data.get("dependencies", []),
            labels=data.get("labels", []),
            metadata=data.get("metadata", {}),
            external_id=data.get("external_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class WorkItemCreate:
    """Data for creating a new work item."""

    title: str
    description: Optional[str] = None
    priority: int = WorkItemPriority.MEDIUM
    phase: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkItemUpdate:
    """Data for updating a work item."""

    status: Optional[WorkItemStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    phase: Optional[str] = None
    labels: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {}
        if self.status is not None:
            result["status"] = self.status.value
        if self.title is not None:
            result["title"] = self.title
        if self.description is not None:
            result["description"] = self.description
        if self.priority is not None:
            result["priority"] = self.priority
        if self.phase is not None:
            result["phase"] = self.phase
        if self.labels is not None:
            result["labels"] = self.labels
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class Project:
    """Represents a project in the work tracker."""

    id: str
    name: str
    description: Optional[str] = None
    directory: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProgressSummary:
    """Summary of work item progress."""

    todo: int = 0
    in_progress: int = 0
    done: int = 0
    blocked: int = 0

    @property
    def total(self) -> int:
        """Total number of work items."""
        return self.todo + self.in_progress + self.done + self.blocked

    @property
    def completion_percentage(self) -> float:
        """Percentage of completed work items."""
        if self.total == 0:
            return 0.0
        return (self.done / self.total) * 100

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "todo": self.todo,
            "in_progress": self.in_progress,
            "done": self.done,
            "blocked": self.blocked,
            "total": self.total,
        }


class WorkTracker(ABC):
    """Abstract interface for work tracking backends.

    This interface defines the contract that all work tracking backends
    must implement. The orchestrator uses this interface to interact with
    different storage systems without knowing the implementation details.

    Implementations:
        - PostgresBackend: PostgreSQL database backend
        - JSONBackend: Local JSON file backend
        - LinearBackend: Linear.app API backend
    """

    @abstractmethod
    async def initialize(self, project_dir: Path) -> Project:
        """Initialize the backend for a project.

        This is called once when starting work on a new project.
        Implementations should create any necessary resources (tables,
        files, Linear projects, etc.).

        Args:
            project_dir: Path to the project directory.

        Returns:
            The created or existing Project.
        """
        pass

    @abstractmethod
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.

        Args:
            project_id: Project identifier.

        Returns:
            The Project or None if not found.
        """
        pass

    @abstractmethod
    async def create_work_item(
        self,
        project_id: str,
        item: WorkItemCreate,
    ) -> WorkItem:
        """Create a new work item.

        Args:
            project_id: Project to create the item in.
            item: Work item data.

        Returns:
            The created WorkItem with generated ID.
        """
        pass

    @abstractmethod
    async def create_work_items_batch(
        self,
        project_id: str,
        items: list[WorkItemCreate],
    ) -> list[WorkItem]:
        """Create multiple work items in a batch.

        This is more efficient than creating items one by one,
        especially for backends that support batch operations.

        Args:
            project_id: Project to create items in.
            items: List of work item data.

        Returns:
            List of created WorkItems.
        """
        pass

    @abstractmethod
    async def get_work_item(self, item_id: str) -> Optional[WorkItem]:
        """Get a work item by ID.

        Args:
            item_id: Work item identifier.

        Returns:
            The WorkItem or None if not found.
        """
        pass

    @abstractmethod
    async def update_work_item(
        self,
        item_id: str,
        updates: WorkItemUpdate,
    ) -> Optional[WorkItem]:
        """Update a work item.

        Args:
            item_id: Work item identifier.
            updates: Fields to update.

        Returns:
            The updated WorkItem or None if not found.
        """
        pass

    @abstractmethod
    async def get_next_work_item(
        self,
        project_id: str,
        phase: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Get the next work item to work on.

        Returns the highest priority TODO item for the project,
        optionally filtered by phase.

        Args:
            project_id: Project identifier.
            phase: Optional phase filter.

        Returns:
            The next WorkItem to work on, or None if no items available.
        """
        pass

    @abstractmethod
    async def list_work_items(
        self,
        project_id: str,
        status: Optional[WorkItemStatus] = None,
        phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkItem]:
        """List work items for a project.

        Args:
            project_id: Project identifier.
            status: Optional status filter.
            phase: Optional phase filter.
            limit: Maximum items to return.
            offset: Offset for pagination.

        Returns:
            List of WorkItems matching the criteria.
        """
        pass

    @abstractmethod
    async def get_progress_summary(
        self,
        project_id: str,
    ) -> ProgressSummary:
        """Get progress summary for a project.

        Args:
            project_id: Project identifier.

        Returns:
            ProgressSummary with item counts by status.
        """
        pass

    @abstractmethod
    async def add_comment(
        self,
        item_id: str,
        content: str,
    ) -> None:
        """Add a comment to a work item.

        Comments are used for handoff notes between agent sessions.

        Args:
            item_id: Work item identifier.
            content: Comment content.
        """
        pass

    @abstractmethod
    async def claim_work_item(
        self,
        item_id: str,
    ) -> Optional[WorkItem]:
        """Claim a work item by setting it to IN_PROGRESS.

        This is a convenience method that atomically claims the item.

        Args:
            item_id: Work item identifier.

        Returns:
            The claimed WorkItem or None if not found/already claimed.
        """
        pass

    @abstractmethod
    async def complete_work_item(
        self,
        item_id: str,
        summary: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Mark a work item as DONE.

        This is a convenience method that marks the item complete
        and optionally adds a completion comment.

        Args:
            item_id: Work item identifier.
            summary: Optional completion summary.

        Returns:
            The completed WorkItem or None if not found.
        """
        pass

    async def close(self) -> None:
        """Close the backend and release resources.

        Override in backends that need cleanup (e.g., database connections).
        """
        pass

    async def __aenter__(self) -> "WorkTracker":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.close()
