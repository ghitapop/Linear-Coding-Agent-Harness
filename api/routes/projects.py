"""Project management endpoints."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    ActionResponse,
    ApproveRequest,
    PhaseStatusResponse,
    ProgressSummary,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ResumeRequest,
    StopRequest,
    WorkItemListResponse,
    WorkItemResponse,
)
from database.connection import get_db_session
from database.models import ProjectStatus, WorkItemStatus
from database.repository import ProjectRepository, WorkItemRepository

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with get_db_session() as session:
        yield session


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    """List all projects.

    Args:
        status_filter: Optional filter by project status.
        limit: Maximum number of results.
        offset: Pagination offset.
        session: Database session.

    Returns:
        List of projects.
    """
    repo = ProjectRepository(session)

    # Parse status filter
    project_status = None
    if status_filter:
        try:
            project_status = ProjectStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    projects = await repo.list_all(
        status=project_status,
        limit=limit,
        offset=offset,
    )

    # Convert to response models
    project_responses = []
    for project in projects:
        project_responses.append(
            ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                current_phase=project.current_phase,
                directory=project.directory,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )

    return ProjectListResponse(
        projects=project_responses,
        total=len(project_responses),  # TODO: Add count query
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project.

    Args:
        request: Project creation request.
        session: Database session.

    Returns:
        Created project.
    """
    repo = ProjectRepository(session)

    # Check for duplicate name
    existing = await repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{request.name}' already exists",
        )

    # Create project
    project = await repo.create(
        name=request.name,
        description=request.idea,
        directory=request.directory,
        config=request.config,
    )

    await session.commit()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_phase=project.current_phase,
        directory=project.directory,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    include_phases: bool = Query(False),
    include_progress: bool = Query(False),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Get a project by ID.

    Args:
        project_id: Project UUID.
        include_phases: Include phase details.
        include_progress: Include work item progress.
        session: Database session.

    Returns:
        Project details.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, include_state=include_phases)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Get phase details if requested
    phases = None
    if include_phases and project.pipeline_state:
        phases = {}
        for name, phase_data in project.pipeline_state.phases.items():
            phases[name] = PhaseStatusResponse(
                name=name,
                status=phase_data.get("status", "pending"),
                started_at=phase_data.get("started_at"),
                completed_at=phase_data.get("completed_at"),
                error=phase_data.get("error"),
                retry_count=phase_data.get("retry_count", 0),
            )

    # Get progress if requested
    progress = None
    if include_progress:
        work_item_repo = WorkItemRepository(session)
        summary = await work_item_repo.get_progress_summary(project_id)
        progress = ProgressSummary(**summary)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_phase=project.current_phase,
        directory=project.directory,
        created_at=project.created_at,
        updated_at=project.updated_at,
        phases=phases,
        progress=progress,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Update a project.

    Args:
        project_id: Project UUID.
        request: Update request.
        session: Database session.

    Returns:
        Updated project.
    """
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Update fields if provided
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.config is not None:
        project.config = request.config

    await session.commit()
    await session.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_phase=project.current_phase,
        directory=project.directory,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a project.

    Args:
        project_id: Project UUID.
        session: Database session.
    """
    repo = ProjectRepository(session)
    deleted = await repo.delete(project_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    await session.commit()


# ============================================================================
# Project Actions
# ============================================================================


@router.post("/{project_id}/resume", response_model=ActionResponse)
async def resume_project(
    project_id: UUID,
    request: ResumeRequest,
    session: AsyncSession = Depends(get_session),
) -> ActionResponse:
    """Resume a paused project.

    Args:
        project_id: Project UUID.
        request: Resume request.
        session: Database session.

    Returns:
        Action result.
    """
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Check if project can be resumed
    if project.status not in [
        ProjectStatus.PAUSED.value,
        ProjectStatus.STOPPED.value,
    ]:
        if not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project cannot be resumed (status: {project.status})",
            )

    # Update status
    await repo.update_status(project_id, ProjectStatus.RUNNING)
    await session.commit()

    return ActionResponse(
        success=True,
        message=f"Project {project_id} is resuming",
        project_id=project_id,
    )


@router.post("/{project_id}/stop", response_model=ActionResponse)
async def stop_project(
    project_id: UUID,
    request: StopRequest,
    session: AsyncSession = Depends(get_session),
) -> ActionResponse:
    """Stop a running project.

    Args:
        project_id: Project UUID.
        request: Stop request.
        session: Database session.

    Returns:
        Action result.
    """
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Check if project is running
    if project.status != ProjectStatus.RUNNING.value:
        if not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project is not running (status: {project.status})",
            )

    # Update status
    new_status = ProjectStatus.STOPPED if request.force else ProjectStatus.STOPPING
    await repo.update_status(project_id, new_status)
    await session.commit()

    return ActionResponse(
        success=True,
        message=f"Project {project_id} is stopping",
        project_id=project_id,
        details={"reason": request.reason},
    )


@router.post("/{project_id}/approve", response_model=ActionResponse)
async def approve_checkpoint(
    project_id: UUID,
    request: ApproveRequest,
    session: AsyncSession = Depends(get_session),
) -> ActionResponse:
    """Approve a checkpoint for a paused project.

    Args:
        project_id: Project UUID.
        request: Approval request.
        session: Database session.

    Returns:
        Action result.
    """
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    if project.status != ProjectStatus.PAUSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is not paused (status: {project.status})",
        )

    if request.approved:
        # Resume after approval
        await repo.update_status(project_id, ProjectStatus.RUNNING)
        message = "Checkpoint approved, project is resuming"
    else:
        # Keep paused or stop
        message = "Checkpoint rejected, project remains paused"

    await session.commit()

    return ActionResponse(
        success=True,
        message=message,
        project_id=project_id,
        details={"approved": request.approved, "comment": request.comment},
    )


# ============================================================================
# Work Items
# ============================================================================


@router.get("/{project_id}/work-items", response_model=WorkItemListResponse)
async def list_work_items(
    project_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    phase: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> WorkItemListResponse:
    """List work items for a project.

    Args:
        project_id: Project UUID.
        status_filter: Optional filter by status.
        phase: Optional filter by phase.
        limit: Maximum number of results.
        offset: Pagination offset.
        session: Database session.

    Returns:
        List of work items.
    """
    # Verify project exists
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Parse status filter
    item_status = None
    if status_filter:
        try:
            item_status = WorkItemStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    repo = WorkItemRepository(session)
    items = await repo.list_by_project(
        project_id=project_id,
        status=item_status,
        phase=phase,
        limit=limit,
        offset=offset,
    )

    item_responses = [
        WorkItemResponse(
            id=item.id,
            project_id=item.project_id,
            title=item.title,
            description=item.description,
            status=item.status,
            priority=item.priority,
            phase=item.phase,
            labels=item.labels,
            created_at=item.created_at,
            updated_at=item.updated_at,
            completed_at=item.completed_at,
        )
        for item in items
    ]

    return WorkItemListResponse(
        items=item_responses,
        total=len(item_responses),
        limit=limit,
        offset=offset,
    )
