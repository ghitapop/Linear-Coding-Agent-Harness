"""Initial schema for Autonomous Orchestrator Framework.

Revision ID: 001
Revises:
Create Date: 2025-12-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for the orchestrator framework."""
    # Projects table
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="not_started"),
        sa.Column("current_phase", sa.String(50), nullable=True),
        sa.Column("directory", sa.String(500), nullable=True),
        sa.Column("config", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_projects_status", "projects", ["status"])

    # Pipeline states table
    op.create_table(
        "pipeline_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("phases", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("last_checkpoint", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shutdown_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("shutdown_reason", sa.String(100), nullable=True),
        sa.Column("agent_snapshots", postgresql.JSON, nullable=True),
        sa.Column("interrupted_work_items", postgresql.JSON, nullable=True),
        sa.Column("last_successful_step", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_pipeline_states_project", "pipeline_states", ["project_id"])

    # Work items table
    op.create_table(
        "work_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="todo"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="3"),
        sa.Column("phase", sa.String(50), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_items.id"),
            nullable=True,
        ),
        sa.Column("dependencies", postgresql.JSON, nullable=True),
        sa.Column("labels", postgresql.JSON, nullable=True),
        sa.Column("metadata", postgresql.JSON, nullable=True),
        sa.Column(
            "external_id",
            sa.String(255),
            nullable=True,
            comment="External system ID (e.g., Linear issue ID)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_work_items_project", "work_items", ["project_id"])
    op.create_index("idx_work_items_status", "work_items", ["status"])
    op.create_index("idx_work_items_priority", "work_items", ["priority"])
    op.create_index("idx_work_items_phase", "work_items", ["phase"])

    # Work item comments table
    op.create_table(
        "work_item_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_work_item_comments_work_item", "work_item_comments", ["work_item_id"])

    # Phase outputs table
    op.create_table(
        "phase_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("output_type", sa.String(100), nullable=True),
        sa.Column("content", postgresql.JSON, nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_phase_outputs_project", "phase_outputs", ["project_id"])
    op.create_index("idx_phase_outputs_phase", "phase_outputs", ["phase"])

    # Session logs table
    op.create_table(
        "session_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(50), nullable=True),
        sa.Column("session_number", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("tool_calls", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_session_logs_project", "session_logs", ["project_id"])
    op.create_index("idx_session_logs_phase", "session_logs", ["phase"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("session_logs")
    op.drop_table("phase_outputs")
    op.drop_table("work_item_comments")
    op.drop_table("work_items")
    op.drop_table("pipeline_states")
    op.drop_table("projects")
