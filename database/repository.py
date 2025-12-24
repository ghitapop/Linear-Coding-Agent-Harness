"""Repository pattern implementation for database access."""

import uuid
from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    PhaseOutput,
    PipelineState,
    Project,
    ProjectStatus,
    SessionLog,
    WorkItem,
    WorkItemComment,
    WorkItemStatus,
)


class ProjectRepository:
    """Repository for Project operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        directory: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name.
            description: Optional project description.
            directory: Optional project directory path.
            config: Optional configuration dict.

        Returns:
            The created Project.
        """
        project = Project(
            name=name,
            description=description,
            directory=directory,
            config=config,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(
        self,
        project_id: uuid.UUID,
        include_state: bool = False,
    ) -> Optional[Project]:
        """Get a project by ID.

        Args:
            project_id: Project UUID.
            include_state: If True, eagerly load pipeline_state.

        Returns:
            The Project or None if not found.
        """
        stmt = select(Project).where(Project.id == project_id)
        if include_state:
            stmt = stmt.options(selectinload(Project.pipeline_state))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Project]:
        """Get a project by name.

        Args:
            name: Project name.

        Returns:
            The Project or None if not found.
        """
        stmt = select(Project).where(Project.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status: Optional[ProjectStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Project]:
        """List all projects.

        Args:
            status: Optional filter by status.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of Projects.
        """
        stmt = select(Project).order_by(Project.updated_at.desc())
        if status:
            stmt = stmt.where(Project.status == status.value)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        project_id: uuid.UUID,
        status: ProjectStatus,
        current_phase: Optional[str] = None,
    ) -> Optional[Project]:
        """Update project status.

        Args:
            project_id: Project UUID.
            status: New status.
            current_phase: Optional current phase.

        Returns:
            Updated Project or None if not found.
        """
        stmt = (
            update(Project)
            .where(Project.id == project_id)
            .values(
                status=status.value,
                current_phase=current_phase,
                updated_at=datetime.utcnow(),
            )
            .returning(Project)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, project_id: uuid.UUID) -> bool:
        """Delete a project.

        Args:
            project_id: Project UUID.

        Returns:
            True if deleted, False if not found.
        """
        project = await self.get_by_id(project_id)
        if project:
            await self._session.delete(project)
            return True
        return False


class PipelineStateRepository:
    """Repository for PipelineState operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        phases: Optional[dict[str, Any]] = None,
    ) -> PipelineState:
        """Create pipeline state for a project.

        Args:
            project_id: Project UUID.
            phases: Initial phases dict.

        Returns:
            The created PipelineState.
        """
        state = PipelineState(
            project_id=project_id,
            phases=phases or {},
            heartbeat=datetime.utcnow(),
        )
        self._session.add(state)
        await self._session.flush()
        return state

    async def get_by_project(
        self,
        project_id: uuid.UUID,
    ) -> Optional[PipelineState]:
        """Get pipeline state by project ID.

        Args:
            project_id: Project UUID.

        Returns:
            The PipelineState or None if not found.
        """
        stmt = select(PipelineState).where(PipelineState.project_id == project_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_heartbeat(
        self,
        project_id: uuid.UUID,
    ) -> Optional[PipelineState]:
        """Update the heartbeat timestamp.

        Args:
            project_id: Project UUID.

        Returns:
            Updated PipelineState or None if not found.
        """
        stmt = (
            update(PipelineState)
            .where(PipelineState.project_id == project_id)
            .values(heartbeat=datetime.utcnow())
            .returning(PipelineState)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_phases(
        self,
        project_id: uuid.UUID,
        phases: dict[str, Any],
    ) -> Optional[PipelineState]:
        """Update phases dict.

        Args:
            project_id: Project UUID.
            phases: New phases dict.

        Returns:
            Updated PipelineState or None if not found.
        """
        stmt = (
            update(PipelineState)
            .where(PipelineState.project_id == project_id)
            .values(
                phases=phases,
                last_checkpoint=datetime.utcnow(),
            )
            .returning(PipelineState)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_shutdown(
        self,
        project_id: uuid.UUID,
        reason: str,
        agent_snapshots: Optional[list[dict[str, Any]]] = None,
        interrupted_work_items: Optional[list[str]] = None,
    ) -> Optional[PipelineState]:
        """Mark pipeline as shutting down.

        Args:
            project_id: Project UUID.
            reason: Shutdown reason.
            agent_snapshots: Optional agent snapshots.
            interrupted_work_items: Optional list of interrupted work item IDs.

        Returns:
            Updated PipelineState or None if not found.
        """
        stmt = (
            update(PipelineState)
            .where(PipelineState.project_id == project_id)
            .values(
                shutdown_requested=True,
                shutdown_reason=reason,
                agent_snapshots=agent_snapshots,
                interrupted_work_items=interrupted_work_items,
                last_checkpoint=datetime.utcnow(),
            )
            .returning(PipelineState)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_shutdown(
        self,
        project_id: uuid.UUID,
    ) -> Optional[PipelineState]:
        """Clear shutdown flag for resume.

        Args:
            project_id: Project UUID.

        Returns:
            Updated PipelineState or None if not found.
        """
        stmt = (
            update(PipelineState)
            .where(PipelineState.project_id == project_id)
            .values(
                shutdown_requested=False,
                shutdown_reason=None,
                agent_snapshots=None,
                interrupted_work_items=None,
            )
            .returning(PipelineState)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class WorkItemRepository:
    """Repository for WorkItem operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        priority: int = 3,
        phase: Optional[str] = None,
        parent_id: Optional[uuid.UUID] = None,
        labels: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        external_id: Optional[str] = None,
    ) -> WorkItem:
        """Create a new work item.

        Args:
            project_id: Project UUID.
            title: Work item title.
            description: Optional description.
            priority: Priority (1=urgent, 4=low).
            phase: Optional phase name.
            parent_id: Optional parent work item ID.
            labels: Optional labels list.
            metadata: Optional metadata dict.
            external_id: Optional external system ID.

        Returns:
            The created WorkItem.
        """
        item = WorkItem(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            phase=phase,
            parent_id=parent_id,
            labels=labels,
            item_metadata=metadata,
            external_id=external_id,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def get_by_id(
        self,
        item_id: uuid.UUID,
        include_comments: bool = False,
    ) -> Optional[WorkItem]:
        """Get a work item by ID.

        Args:
            item_id: Work item UUID.
            include_comments: If True, eagerly load comments.

        Returns:
            The WorkItem or None if not found.
        """
        stmt = select(WorkItem).where(WorkItem.id == item_id)
        if include_comments:
            stmt = stmt.options(selectinload(WorkItem.comments))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_todo(
        self,
        project_id: uuid.UUID,
        phase: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Get the next todo work item by priority.

        Args:
            project_id: Project UUID.
            phase: Optional filter by phase.

        Returns:
            The highest priority TODO WorkItem or None.
        """
        stmt = (
            select(WorkItem)
            .where(WorkItem.project_id == project_id)
            .where(WorkItem.status == WorkItemStatus.TODO.value)
        )
        if phase:
            stmt = stmt.where(WorkItem.phase == phase)
        stmt = stmt.order_by(WorkItem.priority.asc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        status: Optional[WorkItemStatus] = None,
        phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkItem]:
        """List work items for a project.

        Args:
            project_id: Project UUID.
            status: Optional filter by status.
            phase: Optional filter by phase.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of WorkItems.
        """
        stmt = (
            select(WorkItem)
            .where(WorkItem.project_id == project_id)
            .order_by(WorkItem.priority.asc(), WorkItem.created_at.asc())
        )
        if status:
            stmt = stmt.where(WorkItem.status == status.value)
        if phase:
            stmt = stmt.where(WorkItem.phase == phase)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        item_id: uuid.UUID,
        status: WorkItemStatus,
    ) -> Optional[WorkItem]:
        """Update work item status.

        Args:
            item_id: Work item UUID.
            status: New status.

        Returns:
            Updated WorkItem or None if not found.
        """
        values: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow(),
        }
        if status == WorkItemStatus.DONE:
            values["completed_at"] = datetime.utcnow()
        stmt = (
            update(WorkItem)
            .where(WorkItem.id == item_id)
            .values(**values)
            .returning(WorkItem)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_progress_summary(
        self,
        project_id: uuid.UUID,
    ) -> dict[str, int]:
        """Get work item progress summary.

        Args:
            project_id: Project UUID.

        Returns:
            Dict with counts: todo, in_progress, done, blocked, total.
        """
        stmt = (
            select(WorkItem.status, func.count(WorkItem.id))
            .where(WorkItem.project_id == project_id)
            .group_by(WorkItem.status)
        )
        result = await self._session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        return {
            "todo": counts.get(WorkItemStatus.TODO.value, 0),
            "in_progress": counts.get(WorkItemStatus.IN_PROGRESS.value, 0),
            "done": counts.get(WorkItemStatus.DONE.value, 0),
            "blocked": counts.get(WorkItemStatus.BLOCKED.value, 0),
            "total": sum(counts.values()),
        }

    async def add_comment(
        self,
        item_id: uuid.UUID,
        content: str,
    ) -> WorkItemComment:
        """Add a comment to a work item.

        Args:
            item_id: Work item UUID.
            content: Comment content.

        Returns:
            The created WorkItemComment.
        """
        comment = WorkItemComment(
            work_item_id=item_id,
            content=content,
        )
        self._session.add(comment)
        await self._session.flush()
        return comment


class PhaseOutputRepository:
    """Repository for PhaseOutput operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        phase: str,
        output_type: Optional[str] = None,
        content: Optional[dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> PhaseOutput:
        """Create a phase output.

        Args:
            project_id: Project UUID.
            phase: Phase name.
            output_type: Optional output type identifier.
            content: Optional JSON content.
            file_path: Optional file path for file-based output.

        Returns:
            The created PhaseOutput.
        """
        output = PhaseOutput(
            project_id=project_id,
            phase=phase,
            output_type=output_type,
            content=content,
            file_path=file_path,
        )
        self._session.add(output)
        await self._session.flush()
        return output

    async def get_by_phase(
        self,
        project_id: uuid.UUID,
        phase: str,
    ) -> Sequence[PhaseOutput]:
        """Get all outputs for a phase.

        Args:
            project_id: Project UUID.
            phase: Phase name.

        Returns:
            List of PhaseOutputs.
        """
        stmt = (
            select(PhaseOutput)
            .where(PhaseOutput.project_id == project_id)
            .where(PhaseOutput.phase == phase)
            .order_by(PhaseOutput.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest(
        self,
        project_id: uuid.UUID,
        phase: str,
        output_type: Optional[str] = None,
    ) -> Optional[PhaseOutput]:
        """Get the latest output for a phase.

        Args:
            project_id: Project UUID.
            phase: Phase name.
            output_type: Optional filter by output type.

        Returns:
            The latest PhaseOutput or None.
        """
        stmt = (
            select(PhaseOutput)
            .where(PhaseOutput.project_id == project_id)
            .where(PhaseOutput.phase == phase)
        )
        if output_type:
            stmt = stmt.where(PhaseOutput.output_type == output_type)
        stmt = stmt.order_by(PhaseOutput.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class SessionLogRepository:
    """Repository for SessionLog operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        phase: Optional[str] = None,
        session_number: Optional[int] = None,
    ) -> SessionLog:
        """Create a new session log.

        Args:
            project_id: Project UUID.
            phase: Optional phase name.
            session_number: Optional session number.

        Returns:
            The created SessionLog.
        """
        log = SessionLog(
            project_id=project_id,
            phase=phase,
            session_number=session_number,
            started_at=datetime.utcnow(),
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def end_session(
        self,
        log_id: uuid.UUID,
        status: str,
        summary: Optional[str] = None,
        error: Optional[str] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[SessionLog]:
        """End a session log.

        Args:
            log_id: Session log UUID.
            status: Session status.
            summary: Optional session summary.
            error: Optional error message.
            tool_calls: Optional list of tool calls.

        Returns:
            Updated SessionLog or None if not found.
        """
        stmt = (
            update(SessionLog)
            .where(SessionLog.id == log_id)
            .values(
                ended_at=datetime.utcnow(),
                status=status,
                summary=summary,
                error=error,
                tool_calls=tool_calls,
            )
            .returning(SessionLog)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[SessionLog]:
        """List session logs for a project.

        Args:
            project_id: Project UUID.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of SessionLogs.
        """
        stmt = (
            select(SessionLog)
            .where(SessionLog.project_id == project_id)
            .order_by(SessionLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_next_session_number(
        self,
        project_id: uuid.UUID,
    ) -> int:
        """Get the next session number for a project.

        Args:
            project_id: Project UUID.

        Returns:
            The next session number.
        """
        stmt = (
            select(func.max(SessionLog.session_number))
            .where(SessionLog.project_id == project_id)
        )
        result = await self._session.execute(stmt)
        max_num = result.scalar_one_or_none()
        return (max_num or 0) + 1
