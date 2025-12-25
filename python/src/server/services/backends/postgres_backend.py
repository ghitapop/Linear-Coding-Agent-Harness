"""PostgreSQL backend for work tracking.

This backend uses PostgreSQL for persistent storage of work items.
It leverages the existing database models and repository layer.

PostgreSQL is the recommended backend for:
- Production deployments
- Multi-user access
- Data durability and reliability
- Complex queries and filtering

Environment Variables:
    DATABASE_URL: PostgreSQL connection URL
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from server.services.backends.base import (
    ProgressSummary,
    Project,
    WorkItem,
    WorkItemCreate,
    WorkItemStatus,
    WorkItemUpdate,
    WorkTracker,
)
from server.database.connection import DatabaseManager
from server.database.models import WorkItem as DBWorkItem
from server.database.models import WorkItemStatus as DBWorkItemStatus
from server.database.repository import (
    ProjectRepository,
    WorkItemRepository,
)


class PostgresBackend(WorkTracker):
    """PostgreSQL-based work tracker backend.

    This backend uses SQLAlchemy async sessions to interact with
    PostgreSQL. It wraps the repository layer for database operations.

    Attributes:
        database_url: PostgreSQL connection URL.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """Initialize the PostgreSQL backend.

        Args:
            database_url: PostgreSQL connection URL.
                         If not provided, uses DATABASE_URL env var.
        """
        self._db_manager = DatabaseManager.get_instance(database_url=database_url)
        self._project_id: Optional[uuid.UUID] = None

    def _db_to_work_item(self, db_item: DBWorkItem) -> WorkItem:
        """Convert database model to WorkItem."""
        return WorkItem(
            id=str(db_item.id),
            project_id=str(db_item.project_id),
            title=db_item.title,
            description=db_item.description,
            status=WorkItemStatus(db_item.status),
            priority=db_item.priority,
            phase=db_item.phase,
            parent_id=str(db_item.parent_id) if db_item.parent_id else None,
            dependencies=db_item.dependencies or [],
            labels=db_item.labels or [],
            metadata=db_item.item_metadata or {},
            external_id=db_item.external_id,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
            completed_at=db_item.completed_at,
        )

    async def initialize(self, project_dir: Path) -> Project:
        """Initialize the backend for a project."""
        # Ensure tables exist
        await self._db_manager.create_tables()

        async with self._db_manager.session() as session:
            repo = ProjectRepository(session)

            # Check if project exists by directory
            from sqlalchemy import select
            from server.database.models import Project as DBProject

            stmt = select(DBProject).where(DBProject.directory == str(project_dir))
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                self._project_id = existing.id
                await session.commit()
                return Project(
                    id=str(existing.id),
                    name=existing.name,
                    description=existing.description,
                    directory=existing.directory,
                    metadata=existing.config or {},
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )

            # Create new project
            db_project = await repo.create(
                name=project_dir.name,
                description=None,
                directory=str(project_dir),
                config={},
            )
            self._project_id = db_project.id
            await session.commit()

            return Project(
                id=str(db_project.id),
                name=db_project.name,
                description=db_project.description,
                directory=db_project.directory,
                metadata=db_project.config or {},
                created_at=db_project.created_at,
                updated_at=db_project.updated_at,
            )

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        async with self._db_manager.session() as session:
            repo = ProjectRepository(session)
            try:
                db_project = await repo.get_by_id(uuid.UUID(project_id))
            except ValueError:
                return None

            if not db_project:
                return None

            return Project(
                id=str(db_project.id),
                name=db_project.name,
                description=db_project.description,
                directory=db_project.directory,
                metadata=db_project.config or {},
                created_at=db_project.created_at,
                updated_at=db_project.updated_at,
            )

    async def create_work_item(
        self,
        project_id: str,
        item: WorkItemCreate,
    ) -> WorkItem:
        """Create a new work item."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)

            db_item = await repo.create(
                project_id=uuid.UUID(project_id),
                title=item.title,
                description=item.description,
                priority=item.priority,
                phase=item.phase,
                parent_id=uuid.UUID(item.parent_id) if item.parent_id else None,
                labels=item.labels,
                metadata=item.metadata,
            )
            await session.commit()

            return self._db_to_work_item(db_item)

    async def create_work_items_batch(
        self,
        project_id: str,
        items: list[WorkItemCreate],
    ) -> list[WorkItem]:
        """Create multiple work items in a batch."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            results: list[WorkItem] = []

            for item in items:
                db_item = await repo.create(
                    project_id=uuid.UUID(project_id),
                    title=item.title,
                    description=item.description,
                    priority=item.priority,
                    phase=item.phase,
                    parent_id=uuid.UUID(item.parent_id) if item.parent_id else None,
                    labels=item.labels,
                    metadata=item.metadata,
                )
                results.append(self._db_to_work_item(db_item))

            await session.commit()
            return results

    async def get_work_item(self, item_id: str) -> Optional[WorkItem]:
        """Get a work item by ID."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                db_item = await repo.get_by_id(uuid.UUID(item_id))
            except ValueError:
                return None

            if not db_item:
                return None

            return self._db_to_work_item(db_item)

    async def update_work_item(
        self,
        item_id: str,
        updates: WorkItemUpdate,
    ) -> Optional[WorkItem]:
        """Update a work item."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)

            try:
                item_uuid = uuid.UUID(item_id)
            except ValueError:
                return None

            # Get current item
            db_item = await repo.get_by_id(item_uuid)
            if not db_item:
                return None

            # Apply updates
            if updates.status is not None:
                db_item = await repo.update_status(
                    item_uuid,
                    DBWorkItemStatus(updates.status.value),
                )

            # For other updates, we need to do them manually
            if updates.title is not None:
                db_item.title = updates.title
            if updates.description is not None:
                db_item.description = updates.description
            if updates.priority is not None:
                db_item.priority = updates.priority
            if updates.phase is not None:
                db_item.phase = updates.phase
            if updates.labels is not None:
                db_item.labels = updates.labels
            if updates.metadata is not None:
                db_item.item_metadata = updates.metadata

            db_item.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(db_item)

            return self._db_to_work_item(db_item)

    async def get_next_work_item(
        self,
        project_id: str,
        phase: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Get the next work item to work on."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                db_item = await repo.get_next_todo(
                    uuid.UUID(project_id),
                    phase=phase,
                )
            except ValueError:
                return None

            if not db_item:
                return None

            return self._db_to_work_item(db_item)

    async def list_work_items(
        self,
        project_id: str,
        status: Optional[WorkItemStatus] = None,
        phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkItem]:
        """List work items for a project."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                db_status = DBWorkItemStatus(status.value) if status else None
                db_items = await repo.list_by_project(
                    uuid.UUID(project_id),
                    status=db_status,
                    phase=phase,
                    limit=limit,
                    offset=offset,
                )
            except ValueError:
                return []

            return [self._db_to_work_item(item) for item in db_items]

    async def get_progress_summary(
        self,
        project_id: str,
    ) -> ProgressSummary:
        """Get progress summary for a project."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                counts = await repo.get_progress_summary(uuid.UUID(project_id))
            except ValueError:
                return ProgressSummary()

            return ProgressSummary(
                todo=counts.get("todo", 0),
                in_progress=counts.get("in_progress", 0),
                done=counts.get("done", 0),
                blocked=counts.get("blocked", 0),
            )

    async def add_comment(
        self,
        item_id: str,
        content: str,
    ) -> None:
        """Add a comment to a work item."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                await repo.add_comment(uuid.UUID(item_id), content)
                await session.commit()
            except ValueError:
                pass

    async def claim_work_item(
        self,
        item_id: str,
    ) -> Optional[WorkItem]:
        """Claim a work item by setting it to IN_PROGRESS."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                item_uuid = uuid.UUID(item_id)
            except ValueError:
                return None

            # Check current status
            db_item = await repo.get_by_id(item_uuid)
            if not db_item or db_item.status != DBWorkItemStatus.TODO.value:
                return None

            db_item = await repo.update_status(item_uuid, DBWorkItemStatus.IN_PROGRESS)
            await session.commit()

            if db_item:
                return self._db_to_work_item(db_item)
            return None

    async def complete_work_item(
        self,
        item_id: str,
        summary: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Mark a work item as DONE."""
        async with self._db_manager.session() as session:
            repo = WorkItemRepository(session)
            try:
                item_uuid = uuid.UUID(item_id)
            except ValueError:
                return None

            # Add completion comment
            if summary:
                await repo.add_comment(item_uuid, f"Completed: {summary}")

            # Update status
            db_item = await repo.update_status(item_uuid, DBWorkItemStatus.DONE)
            await session.commit()

            if db_item:
                return self._db_to_work_item(db_item)
            return None

    async def close(self) -> None:
        """Close the database connection."""
        # Note: We don't close the singleton manager here as it might be used elsewhere
        pass
