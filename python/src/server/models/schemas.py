"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Project Schemas
# ============================================================================


class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""

    name: str = Field(min_length=1, max_length=255)
    idea: str = Field(min_length=1, description="The project idea/description")
    directory: Optional[str] = Field(default=None, description="Project directory path")
    config: Optional[dict[str, Any]] = Field(default=None, description="Project configuration")


class ProjectUpdate(BaseModel):
    """Request schema for updating a project."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class PhaseStatusResponse(BaseModel):
    """Response schema for phase status."""

    name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0


class ProgressSummary(BaseModel):
    """Response schema for work item progress."""

    todo: int = 0
    in_progress: int = 0
    done: int = 0
    blocked: int = 0
    total: int = 0

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.done / self.total) * 100


class ProjectResponse(BaseModel):
    """Response schema for a project."""

    id: UUID
    name: str
    description: Optional[str] = None
    status: str
    current_phase: Optional[str] = None
    directory: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    phases: Optional[dict[str, PhaseStatusResponse]] = None
    progress: Optional[ProgressSummary] = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Response schema for list of projects."""

    projects: list[ProjectResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Work Item Schemas
# ============================================================================


class WorkItemCreate(BaseModel):
    """Request schema for creating a work item."""

    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=4)
    phase: Optional[str] = None
    labels: Optional[list[str]] = None


class WorkItemUpdate(BaseModel):
    """Request schema for updating a work item."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=4)


class WorkItemResponse(BaseModel):
    """Response schema for a work item."""

    id: UUID
    project_id: UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: int
    phase: Optional[str] = None
    labels: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkItemListResponse(BaseModel):
    """Response schema for list of work items."""

    items: list[WorkItemResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Action Schemas
# ============================================================================


class ResumeRequest(BaseModel):
    """Request schema for resuming a project."""

    force: bool = Field(default=False, description="Force resume even if state is invalid")


class StopRequest(BaseModel):
    """Request schema for stopping a project."""

    reason: str = Field(default="user_request", description="Reason for stopping")
    force: bool = Field(default=False, description="Force stop without waiting")


class ApproveRequest(BaseModel):
    """Request schema for approving a checkpoint."""

    approved: bool = True
    comment: Optional[str] = None


class ActionResponse(BaseModel):
    """Response schema for actions."""

    success: bool
    message: str
    project_id: Optional[UUID] = None
    details: Optional[dict[str, Any]] = None


# ============================================================================
# Health Schemas
# ============================================================================


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "connected"
    uptime_seconds: float = 0.0


class DetailedHealthResponse(HealthResponse):
    """Response schema for detailed health check."""

    database_latency_ms: Optional[float] = None
    active_projects: int = 0
    running_agents: int = 0
    memory_usage_mb: Optional[float] = None
