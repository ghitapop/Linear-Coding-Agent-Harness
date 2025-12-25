"""Pydantic configuration models for the Autonomous Orchestrator Framework."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BackendType(str, Enum):
    """Work tracker backend types."""

    JSON = "json"
    LINEAR = "linear"
    POSTGRES = "postgres"


class PlanningPattern(str, Enum):
    """Planning pattern for phases."""

    SINGLE = "single"  # Single agent
    SWARM = "swarm"  # Multiple parallel agents


class AutonomyMode(str, Enum):
    """Autonomy mode for orchestrator."""

    FULL = "full"  # Fully autonomous, no pauses
    CHECKPOINT = "checkpoint"  # Pause at checkpoints for approval


class PhaseConfig(BaseModel):
    """Configuration for a single phase."""

    enabled: bool = True
    pattern: PlanningPattern = PlanningPattern.SINGLE
    checkpoint_pause: bool = False
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_minutes: int = Field(default=60, ge=1, le=1440)


class ProjectConfig(BaseModel):
    """Project-specific configuration."""

    name: str = Field(min_length=1, max_length=255)
    directory: Path = Field(default=Path("."))
    description: Optional[str] = None

    @field_validator("directory", mode="before")
    @classmethod
    def convert_to_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v


class BackendConfig(BaseModel):
    """Work tracker backend configuration."""

    type: BackendType = BackendType.POSTGRES
    database_url: Optional[str] = None
    linear_api_key: Optional[str] = None
    json_file_path: Optional[Path] = None

    @field_validator("json_file_path", mode="before")
    @classmethod
    def convert_json_path(cls, v: str | Path | None) -> Path | None:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v


class AgentConfig(BaseModel):
    """Agent-specific configuration."""

    model: str = Field(default="claude-opus-4-5-20251101")
    max_sessions: int = Field(default=1000, ge=1, le=10000)
    session_timeout_minutes: int = Field(default=120, ge=1, le=480)


class ErrorRecoveryConfig(BaseModel):
    """Error recovery configuration."""

    max_consecutive_errors: int = Field(default=3, ge=1, le=10)
    stall_timeout_minutes: int = Field(default=30, ge=5, le=120)
    retry_delay_seconds: int = Field(default=5, ge=1, le=60)


class MCPServerConfig(BaseModel):
    """Configuration for an HTTP/SSE MCP server."""

    type: str = Field(description="Transport type: 'http' or 'sse'")
    url: str = Field(description="MCP server URL")
    headers: Optional[dict[str, str]] = Field(default=None, description="Optional headers")


class SwarmConfig(BaseModel):
    """Configuration for swarm agent execution.

    Only HTTP/SSE MCP servers are supported for swarm agents.
    stdio servers (command+args) cause "Control request timeout: initialize"
    errors when multiple agents try to spawn processes concurrently.
    """

    max_concurrent: int = Field(default=3, ge=1, le=10)
    stagger_delay_seconds: float = Field(default=1.0, ge=0, le=30)
    mcp_servers: Optional[dict[str, MCPServerConfig]] = Field(
        default=None,
        description="HTTP/SSE MCP servers for swarm agents (e.g., Archon for docs)",
    )
    mcp_tools: Optional[list[str]] = Field(
        default=None,
        description="MCP tool names to allow (e.g., mcp__archon__search_docs)",
    )


class PhasesConfig(BaseModel):
    """Configuration for all phases."""

    ideation: PhaseConfig = Field(default_factory=lambda: PhaseConfig(
        pattern=PlanningPattern.SWARM,
        checkpoint_pause=True,
    ))
    architecture: PhaseConfig = Field(default_factory=lambda: PhaseConfig(
        pattern=PlanningPattern.SWARM,
        checkpoint_pause=True,
    ))
    task_breakdown: PhaseConfig = Field(default_factory=lambda: PhaseConfig(
        checkpoint_pause=True,
    ))
    initialize: PhaseConfig = Field(default_factory=PhaseConfig)
    implement: PhaseConfig = Field(default_factory=PhaseConfig)
    testing: PhaseConfig = Field(default_factory=lambda: PhaseConfig(enabled=False))
    deploy: PhaseConfig = Field(default_factory=lambda: PhaseConfig(enabled=False))


class OrchestratorConfig(BaseModel):
    """Main orchestrator configuration."""

    project: ProjectConfig
    backend: BackendConfig = Field(default_factory=BackendConfig)
    autonomy: AutonomyMode = AutonomyMode.CHECKPOINT
    phases: PhasesConfig = Field(default_factory=PhasesConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    error_recovery: ErrorRecoveryConfig = Field(default_factory=ErrorRecoveryConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)

    # Database settings
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL (overrides backend.database_url)",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def use_backend_url_if_none(cls, v: str | None, info: object) -> str | None:
        """Use backend database_url if main one is not set."""
        return v
