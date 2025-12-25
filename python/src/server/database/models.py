"""SQLAlchemy models for the Autonomous Orchestrator Framework."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class ProjectStatus(str, Enum):
    """Project status values."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkItemStatus(str, Enum):
    """Work item status values."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Project(Base):
    """Project model - represents a software development project."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ProjectStatus.NOT_STARTED.value,
        nullable=False,
    )
    current_phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    directory: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    pipeline_state: Mapped[Optional["PipelineState"]] = relationship(
        "PipelineState",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    work_items: Mapped[list["WorkItem"]] = relationship(
        "WorkItem",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    phase_outputs: Mapped[list["PhaseOutput"]] = relationship(
        "PhaseOutput",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    session_logs: Mapped[list["SessionLog"]] = relationship(
        "SessionLog",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_projects_status", "status"),
    )


class PipelineState(Base):
    """Pipeline state model - tracks the state of a project's pipeline."""

    __tablename__ = "pipeline_states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    phases: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_checkpoint: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    shutdown_requested: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    shutdown_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_snapshots: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
    )
    interrupted_work_items: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
    )
    last_successful_step: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="pipeline_state")

    __table_args__ = (
        Index("idx_pipeline_states_project", "project_id"),
    )


class WorkItem(Base):
    """Work item model - represents a feature/task to implement."""

    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=WorkItemStatus.TODO.value,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id"),
        nullable=True,
    )
    dependencies: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    labels: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    item_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Keep column name as 'metadata' in DB
        JSON,
        nullable=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="External system ID (e.g., Linear issue ID)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="work_items")
    parent: Mapped[Optional["WorkItem"]] = relationship(
        "WorkItem",
        remote_side=[id],
        backref="children",
    )
    comments: Mapped[list["WorkItemComment"]] = relationship(
        "WorkItemComment",
        back_populates="work_item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_work_items_project", "project_id"),
        Index("idx_work_items_status", "status"),
        Index("idx_work_items_priority", "priority"),
        Index("idx_work_items_phase", "phase"),
    )


class WorkItemComment(Base):
    """Work item comment model - for handoff notes between sessions."""

    __tablename__ = "work_item_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    work_item: Mapped["WorkItem"] = relationship(
        "WorkItem",
        back_populates="comments",
    )

    __table_args__ = (
        Index("idx_work_item_comments_work_item", "work_item_id"),
    )


class PhaseOutput(Base):
    """Phase output model - stores artifacts produced by phases."""

    __tablename__ = "phase_outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    output_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="phase_outputs")

    __table_args__ = (
        Index("idx_phase_outputs_project", "project_id"),
        Index("idx_phase_outputs_phase", "phase"),
    )


class SessionLog(Base):
    """Session log model - for debugging and audit."""

    __tablename__ = "session_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    session_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="session_logs")

    __table_args__ = (
        Index("idx_session_logs_project", "project_id"),
        Index("idx_session_logs_phase", "phase"),
    )
