"""Base phase class for the Autonomous Orchestrator Framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PlanningPattern(str, Enum):
    """Planning pattern for phase execution."""

    SINGLE = "single"  # Single agent
    SWARM = "swarm"  # Multiple parallel agents


class PhaseStatus(str, Enum):
    """Status of a phase execution."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_APPROVAL = "needs_approval"


@dataclass
class PhaseConfig:
    """Configuration for a phase."""

    enabled: bool = True
    pattern: PlanningPattern = PlanningPattern.SINGLE
    checkpoint_pause: bool = False
    max_retries: int = 3
    timeout_minutes: int = 60
    model: str = "claude-opus-4-5-20251101"


@dataclass
class PhaseResult:
    """Result of a phase execution."""

    status: PhaseStatus
    output: Any = None
    output_reference: Optional[str] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if phase succeeded."""
        return self.status == PhaseStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        """Check if phase failed."""
        return self.status == PhaseStatus.FAILED

    @property
    def needs_approval(self) -> bool:
        """Check if phase needs user approval."""
        return self.status == PhaseStatus.NEEDS_APPROVAL


class Phase(ABC):
    """Abstract base class for pipeline phases.

    Each phase represents a distinct step in the software development
    pipeline (ideation, architecture, implementation, etc.).
    """

    # Phase metadata - override in subclasses
    name: str = "base"
    display_name: str = "Base Phase"
    description: str = "Base phase class"

    def __init__(self, config: Optional[PhaseConfig] = None) -> None:
        """Initialize the phase.

        Args:
            config: Optional phase configuration.
        """
        self.config = config or PhaseConfig()

    @abstractmethod
    async def run(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> PhaseResult:
        """Run the phase.

        Args:
            input_data: Input data from previous phase or user.
            project_dir: Project directory path.
            context: Optional context dict with additional info.

        Returns:
            PhaseResult with status and output.
        """
        pass

    def get_prompts(self) -> list[str]:
        """Get prompts for this phase.

        Override in subclasses to return phase-specific prompts.
        For swarm patterns, return multiple prompts (one per agent).

        Returns:
            List of prompt strings.
        """
        return []

    def should_skip(self, context: Optional[dict[str, Any]] = None) -> bool:
        """Check if this phase should be skipped.

        Override in subclasses for custom skip logic.

        Args:
            context: Optional context dict.

        Returns:
            True if phase should be skipped.
        """
        return not self.config.enabled

    async def validate_input(
        self,
        input_data: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Validate input data for this phase.

        Override in subclasses for custom validation.

        Args:
            input_data: Input data to validate.
            context: Optional context dict.

        Returns:
            True if input is valid.
        """
        return True

    async def prepare(
        self,
        input_data: Any,
        project_dir: Path,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Prepare for phase execution.

        Override in subclasses for custom preparation logic.

        Args:
            input_data: Input data from previous phase.
            project_dir: Project directory path.
            context: Optional context dict.

        Returns:
            Prepared context dict.
        """
        return context or {}

    async def cleanup(
        self,
        result: PhaseResult,
        project_dir: Path,
    ) -> None:
        """Cleanup after phase execution.

        Override in subclasses for custom cleanup logic.

        Args:
            result: Phase result.
            project_dir: Project directory path.
        """
        pass

    def __str__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"<{self.__class__.__name__} name={self.name} enabled={self.config.enabled}>"
