"""Database module for the Autonomous Orchestrator Framework."""

from database.connection import DatabaseManager, get_db_session
from database.models import (
    Base,
    PhaseOutput,
    PipelineState,
    Project,
    SessionLog,
    WorkItem,
    WorkItemComment,
)
from database.repository import (
    PhaseOutputRepository,
    PipelineStateRepository,
    ProjectRepository,
    SessionLogRepository,
    WorkItemRepository,
)

__all__ = [
    # Models
    "Base",
    "Project",
    "PipelineState",
    "WorkItem",
    "WorkItemComment",
    "PhaseOutput",
    "SessionLog",
    # Connection
    "DatabaseManager",
    "get_db_session",
    # Repositories
    "ProjectRepository",
    "PipelineStateRepository",
    "WorkItemRepository",
    "PhaseOutputRepository",
    "SessionLogRepository",
]
