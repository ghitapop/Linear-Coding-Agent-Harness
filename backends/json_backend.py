"""JSON file backend for work tracking.

This backend stores work items in a local JSON file. It's useful for:
- Development and testing
- Simple single-user deployments
- Offline usage without a database

The JSON file structure:
{
    "version": 1,
    "project": {...},
    "work_items": [...],
    "comments": {...}
}
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from backends.base import (
    ProgressSummary,
    Project,
    WorkItem,
    WorkItemCreate,
    WorkItemStatus,
    WorkItemUpdate,
    WorkTracker,
)


class JSONBackend(WorkTracker):
    """JSON file-based work tracker backend.

    This backend persists work items to a local JSON file.
    All operations are synchronous file I/O wrapped in async methods.

    Thread Safety:
        This implementation is NOT thread-safe. For concurrent access,
        use the PostgresBackend or implement file locking.

    Attributes:
        file_path: Path to the JSON file.
    """

    VERSION = 1

    def __init__(self, file_path: Path | str) -> None:
        """Initialize the JSON backend.

        Args:
            file_path: Path to the JSON file for storage.
        """
        self._file_path = Path(file_path) if isinstance(file_path, str) else file_path
        self._data: dict[str, Any] = self._load_or_create()

    def _load_or_create(self) -> dict[str, Any]:
        """Load existing data or create empty structure."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Validate version
                if data.get("version") != self.VERSION:
                    # Migration could be added here
                    pass
                return data
            except (json.JSONDecodeError, IOError):
                pass

        # Create empty structure
        return {
            "version": self.VERSION,
            "project": None,
            "work_items": [],
            "comments": {},  # item_id -> [comments]
        }

    def _save(self) -> None:
        """Save data to file atomically."""
        # Ensure parent directory exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic)
        temp_path = self._file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

        # Atomic rename
        temp_path.replace(self._file_path)

    def _find_item_index(self, item_id: str) -> int:
        """Find index of work item by ID, returns -1 if not found."""
        for i, item in enumerate(self._data["work_items"]):
            if item["id"] == item_id:
                return i
        return -1

    async def initialize(self, project_dir: Path) -> Project:
        """Initialize the backend for a project."""
        # Create project if doesn't exist
        if self._data["project"] is None:
            project_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            self._data["project"] = {
                "id": project_id,
                "name": project_dir.name,
                "description": None,
                "directory": str(project_dir),
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            }
            self._save()

        proj = self._data["project"]
        return Project(
            id=proj["id"],
            name=proj["name"],
            description=proj.get("description"),
            directory=proj.get("directory"),
            metadata=proj.get("metadata", {}),
            created_at=datetime.fromisoformat(proj["created_at"]) if proj.get("created_at") else None,
            updated_at=datetime.fromisoformat(proj["updated_at"]) if proj.get("updated_at") else None,
        )

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        proj = self._data.get("project")
        if proj and proj["id"] == project_id:
            return Project(
                id=proj["id"],
                name=proj["name"],
                description=proj.get("description"),
                directory=proj.get("directory"),
                metadata=proj.get("metadata", {}),
                created_at=datetime.fromisoformat(proj["created_at"]) if proj.get("created_at") else None,
                updated_at=datetime.fromisoformat(proj["updated_at"]) if proj.get("updated_at") else None,
            )
        return None

    async def create_work_item(
        self,
        project_id: str,
        item: WorkItemCreate,
    ) -> WorkItem:
        """Create a new work item."""
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()

        work_item = WorkItem(
            id=item_id,
            project_id=project_id,
            title=item.title,
            description=item.description,
            status=WorkItemStatus.TODO,
            priority=item.priority,
            phase=item.phase,
            parent_id=item.parent_id,
            dependencies=item.dependencies,
            labels=item.labels,
            metadata=item.metadata,
            created_at=now,
            updated_at=now,
        )

        self._data["work_items"].append(work_item.to_dict())
        self._save()

        return work_item

    async def create_work_items_batch(
        self,
        project_id: str,
        items: list[WorkItemCreate],
    ) -> list[WorkItem]:
        """Create multiple work items in a batch."""
        created: list[WorkItem] = []
        now = datetime.utcnow()

        for item in items:
            item_id = str(uuid.uuid4())
            work_item = WorkItem(
                id=item_id,
                project_id=project_id,
                title=item.title,
                description=item.description,
                status=WorkItemStatus.TODO,
                priority=item.priority,
                phase=item.phase,
                parent_id=item.parent_id,
                dependencies=item.dependencies,
                labels=item.labels,
                metadata=item.metadata,
                created_at=now,
                updated_at=now,
            )
            self._data["work_items"].append(work_item.to_dict())
            created.append(work_item)

        self._save()
        return created

    async def get_work_item(self, item_id: str) -> Optional[WorkItem]:
        """Get a work item by ID."""
        idx = self._find_item_index(item_id)
        if idx >= 0:
            return WorkItem.from_dict(self._data["work_items"][idx])
        return None

    async def update_work_item(
        self,
        item_id: str,
        updates: WorkItemUpdate,
    ) -> Optional[WorkItem]:
        """Update a work item."""
        idx = self._find_item_index(item_id)
        if idx < 0:
            return None

        item_data = self._data["work_items"][idx]
        update_dict = updates.to_dict()

        # Apply updates
        for key, value in update_dict.items():
            item_data[key] = value

        # Update timestamp
        item_data["updated_at"] = datetime.utcnow().isoformat()

        # Set completed_at if marking as done
        if updates.status == WorkItemStatus.DONE:
            item_data["completed_at"] = datetime.utcnow().isoformat()

        self._save()
        return WorkItem.from_dict(item_data)

    async def get_next_work_item(
        self,
        project_id: str,
        phase: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Get the next work item to work on."""
        candidates: list[dict[str, Any]] = []

        for item in self._data["work_items"]:
            if item["project_id"] != project_id:
                continue
            if item["status"] != WorkItemStatus.TODO.value:
                continue
            if phase and item.get("phase") != phase:
                continue
            candidates.append(item)

        if not candidates:
            return None

        # Sort by priority (lower number = higher priority)
        candidates.sort(key=lambda x: x.get("priority", 3))
        return WorkItem.from_dict(candidates[0])

    async def list_work_items(
        self,
        project_id: str,
        status: Optional[WorkItemStatus] = None,
        phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkItem]:
        """List work items for a project."""
        results: list[WorkItem] = []

        for item in self._data["work_items"]:
            if item["project_id"] != project_id:
                continue
            if status and item["status"] != status.value:
                continue
            if phase and item.get("phase") != phase:
                continue
            results.append(WorkItem.from_dict(item))

        # Sort by priority then created_at
        results.sort(key=lambda x: (x.priority, x.created_at or datetime.min))

        # Apply pagination
        return results[offset : offset + limit]

    async def get_progress_summary(
        self,
        project_id: str,
    ) -> ProgressSummary:
        """Get progress summary for a project."""
        counts = {
            WorkItemStatus.TODO.value: 0,
            WorkItemStatus.IN_PROGRESS.value: 0,
            WorkItemStatus.DONE.value: 0,
            WorkItemStatus.BLOCKED.value: 0,
        }

        for item in self._data["work_items"]:
            if item["project_id"] == project_id:
                status = item.get("status", WorkItemStatus.TODO.value)
                if status in counts:
                    counts[status] += 1

        return ProgressSummary(
            todo=counts[WorkItemStatus.TODO.value],
            in_progress=counts[WorkItemStatus.IN_PROGRESS.value],
            done=counts[WorkItemStatus.DONE.value],
            blocked=counts[WorkItemStatus.BLOCKED.value],
        )

    async def add_comment(
        self,
        item_id: str,
        content: str,
    ) -> None:
        """Add a comment to a work item."""
        if item_id not in self._data["comments"]:
            self._data["comments"][item_id] = []

        self._data["comments"][item_id].append({
            "id": str(uuid.uuid4()),
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
        })
        self._save()

    async def claim_work_item(
        self,
        item_id: str,
    ) -> Optional[WorkItem]:
        """Claim a work item by setting it to IN_PROGRESS."""
        idx = self._find_item_index(item_id)
        if idx < 0:
            return None

        item_data = self._data["work_items"][idx]

        # Only claim if currently TODO
        if item_data["status"] != WorkItemStatus.TODO.value:
            return None

        item_data["status"] = WorkItemStatus.IN_PROGRESS.value
        item_data["updated_at"] = datetime.utcnow().isoformat()
        self._save()

        return WorkItem.from_dict(item_data)

    async def complete_work_item(
        self,
        item_id: str,
        summary: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Mark a work item as DONE."""
        idx = self._find_item_index(item_id)
        if idx < 0:
            return None

        item_data = self._data["work_items"][idx]
        now = datetime.utcnow().isoformat()

        item_data["status"] = WorkItemStatus.DONE.value
        item_data["updated_at"] = now
        item_data["completed_at"] = now

        # Add completion comment if summary provided
        if summary:
            await self.add_comment(item_id, f"Completed: {summary}")

        self._save()
        return WorkItem.from_dict(item_data)

    def get_comments(self, item_id: str) -> list[dict[str, Any]]:
        """Get comments for a work item (sync method for convenience)."""
        return self._data["comments"].get(item_id, [])
