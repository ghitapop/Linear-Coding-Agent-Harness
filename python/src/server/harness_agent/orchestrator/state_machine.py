"""Pipeline state machine for the Autonomous Orchestrator Framework."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PipelineStatus(str, Enum):
    """Pipeline status values."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, Enum):
    """Phase status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentSnapshot:
    """Snapshot of an agent's state for resume."""

    agent_id: str
    phase: str
    started_at: datetime
    last_activity: datetime
    current_work_item: Optional[str] = None
    last_tool_call: Optional[str] = None
    conversation_summary: str = ""
    can_resume: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_id": self.agent_id,
            "phase": self.phase,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "current_work_item": self.current_work_item,
            "last_tool_call": self.last_tool_call,
            "conversation_summary": self.conversation_summary,
            "can_resume": self.can_resume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSnapshot":
        """Create from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            phase=data["phase"],
            started_at=datetime.fromisoformat(data["started_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            current_work_item=data.get("current_work_item"),
            last_tool_call=data.get("last_tool_call"),
            conversation_summary=data.get("conversation_summary", ""),
            can_resume=data.get("can_resume", True),
        )


@dataclass
class PhaseState:
    """State of a single phase."""

    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    output_reference: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "output_reference": self.output_reference,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseState":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            status=PhaseStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
            output_reference=data.get("output_reference"),
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class PipelineState:
    """Complete state of the pipeline."""

    project_id: str
    status: PipelineStatus = PipelineStatus.NOT_STARTED
    current_phase: Optional[str] = None
    phases: dict[str, PhaseState] = field(default_factory=dict)

    # Shutdown/Resume support
    last_checkpoint: Optional[datetime] = None
    heartbeat: Optional[datetime] = None
    shutdown_requested: bool = False
    shutdown_reason: Optional[str] = None

    # Agent snapshots for resume
    agent_snapshots: list[AgentSnapshot] = field(default_factory=list)

    # Recovery info
    interrupted_work_items: list[str] = field(default_factory=list)
    last_successful_step: Optional[str] = None

    # Rejection feedback for retry with user guidance
    rejection_feedback: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_id": self.project_id,
            "status": self.status.value,
            "current_phase": self.current_phase,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "last_checkpoint": self.last_checkpoint.isoformat() if self.last_checkpoint else None,
            "heartbeat": self.heartbeat.isoformat() if self.heartbeat else None,
            "shutdown_requested": self.shutdown_requested,
            "shutdown_reason": self.shutdown_reason,
            "agent_snapshots": [s.to_dict() for s in self.agent_snapshots],
            "interrupted_work_items": self.interrupted_work_items,
            "last_successful_step": self.last_successful_step,
            "rejection_feedback": self.rejection_feedback,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineState":
        """Create from dictionary."""
        phases = {
            k: PhaseState.from_dict(v)
            for k, v in data.get("phases", {}).items()
        }
        agent_snapshots = [
            AgentSnapshot.from_dict(s)
            for s in data.get("agent_snapshots", [])
        ]
        return cls(
            project_id=data["project_id"],
            status=PipelineStatus(data.get("status", "not_started")),
            current_phase=data.get("current_phase"),
            phases=phases,
            last_checkpoint=datetime.fromisoformat(data["last_checkpoint"]) if data.get("last_checkpoint") else None,
            heartbeat=datetime.fromisoformat(data["heartbeat"]) if data.get("heartbeat") else None,
            shutdown_requested=data.get("shutdown_requested", False),
            shutdown_reason=data.get("shutdown_reason"),
            agent_snapshots=agent_snapshots,
            interrupted_work_items=data.get("interrupted_work_items", []),
            last_successful_step=data.get("last_successful_step"),
            rejection_feedback=data.get("rejection_feedback"),
        )


# Default phase order
DEFAULT_PHASES = [
    "ideation",
    "architecture",
    "task_breakdown",
    "initialize",
    "implement",
    "testing",
    "deploy",
]


class StateMachine:
    """Manages pipeline state and transitions."""

    STATE_FILENAME = ".orchestrator_state.json"

    def __init__(
        self,
        project_dir: Path,
        project_id: Optional[str] = None,
        phases: Optional[list[str]] = None,
    ) -> None:
        """Initialize the state machine.

        Args:
            project_dir: Project directory for state file.
            project_id: Optional project ID. Generated if not provided.
            phases: Optional list of phase names. Uses DEFAULT_PHASES if not provided.
        """
        self._project_dir = project_dir
        self._state_path = project_dir / self.STATE_FILENAME
        self._phases = phases or DEFAULT_PHASES

        # Load existing state or create new
        if self._state_path.exists():
            self._state = self._load_state()
        else:
            self._state = self._create_initial_state(
                project_id or str(uuid.uuid4())
            )

    @property
    def state(self) -> PipelineState:
        """Get the current pipeline state."""
        return self._state

    @property
    def state_path(self) -> Path:
        """Get the state file path."""
        return self._state_path

    def _create_initial_state(self, project_id: str) -> PipelineState:
        """Create initial pipeline state.

        Args:
            project_id: Project identifier.

        Returns:
            New PipelineState with phases initialized.
        """
        phases = {
            name: PhaseState(name=name)
            for name in self._phases
        }
        return PipelineState(
            project_id=project_id,
            phases=phases,
            heartbeat=datetime.utcnow(),
        )

    def _load_state(self) -> PipelineState:
        """Load state from file.

        Returns:
            Loaded PipelineState.

        Raises:
            FileNotFoundError: If state file doesn't exist.
            json.JSONDecodeError: If state file is invalid JSON.
        """
        with open(self._state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PipelineState.from_dict(data)

    def save(self) -> None:
        """Save state to file atomically.

        Writes to a temp file first, then renames to prevent corruption.
        """
        self._state.last_checkpoint = datetime.utcnow()
        temp_path = self._state_path.with_suffix(".tmp")

        # Write to temp file
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._state.to_dict(), f, indent=2)

        # Verify JSON is valid
        with open(temp_path, "r", encoding="utf-8") as f:
            json.load(f)

        # Atomic rename
        temp_path.replace(self._state_path)

    def set_status(self, status: PipelineStatus) -> None:
        """Set pipeline status.

        Args:
            status: New status.
        """
        self._state.status = status
        self.save()

    def start_phase(self, phase_name: str) -> PhaseState:
        """Start a phase.

        Args:
            phase_name: Name of the phase to start.

        Returns:
            The updated PhaseState.

        Raises:
            ValueError: If phase doesn't exist.
        """
        if phase_name not in self._state.phases:
            raise ValueError(f"Unknown phase: {phase_name}")

        phase = self._state.phases[phase_name]
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.utcnow()
        phase.error = None

        self._state.current_phase = phase_name
        self._state.status = PipelineStatus.RUNNING
        self.save()

        return phase

    def complete_phase(
        self,
        phase_name: str,
        output_reference: Optional[str] = None,
    ) -> PhaseState:
        """Complete a phase.

        Args:
            phase_name: Name of the phase to complete.
            output_reference: Optional reference to phase output.

        Returns:
            The updated PhaseState.

        Raises:
            ValueError: If phase doesn't exist.
        """
        if phase_name not in self._state.phases:
            raise ValueError(f"Unknown phase: {phase_name}")

        phase = self._state.phases[phase_name]
        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.utcnow()
        phase.output_reference = output_reference

        self._state.last_successful_step = phase_name
        self.save()

        return phase

    def fail_phase(self, phase_name: str, error: str) -> PhaseState:
        """Mark a phase as failed.

        Args:
            phase_name: Name of the phase.
            error: Error message.

        Returns:
            The updated PhaseState.

        Raises:
            ValueError: If phase doesn't exist.
        """
        if phase_name not in self._state.phases:
            raise ValueError(f"Unknown phase: {phase_name}")

        phase = self._state.phases[phase_name]
        phase.status = PhaseStatus.FAILED
        phase.error = error
        phase.retry_count += 1
        self.save()

        return phase

    def skip_phase(self, phase_name: str) -> PhaseState:
        """Skip a phase.

        Args:
            phase_name: Name of the phase to skip.

        Returns:
            The updated PhaseState.

        Raises:
            ValueError: If phase doesn't exist.
        """
        if phase_name not in self._state.phases:
            raise ValueError(f"Unknown phase: {phase_name}")

        phase = self._state.phases[phase_name]
        phase.status = PhaseStatus.SKIPPED
        self.save()

        return phase

    def get_next_phase(self) -> Optional[str]:
        """Get the next phase to run.

        Returns:
            Name of the next pending phase, or None if all done.
        """
        for phase_name in self._phases:
            phase = self._state.phases.get(phase_name)
            if phase and phase.status == PhaseStatus.PENDING:
                return phase_name
        return None

    def is_complete(self) -> bool:
        """Check if the pipeline is complete.

        Returns:
            True if all phases are completed or skipped.
        """
        return all(
            phase.status in [PhaseStatus.COMPLETED, PhaseStatus.SKIPPED]
            for phase in self._state.phases.values()
        )

    def update_heartbeat(self) -> None:
        """Update the heartbeat timestamp."""
        self._state.heartbeat = datetime.utcnow()
        self.save()

    def add_agent_snapshot(self, snapshot: AgentSnapshot) -> None:
        """Add an agent snapshot.

        Args:
            snapshot: Agent snapshot to add.
        """
        self._state.agent_snapshots.append(snapshot)
        self.save()

    def clear_agent_snapshots(self) -> None:
        """Clear all agent snapshots."""
        self._state.agent_snapshots = []
        self.save()

    def add_interrupted_work_item(self, item_id: str) -> None:
        """Add an interrupted work item ID.

        Args:
            item_id: Work item ID that was interrupted.
        """
        if item_id not in self._state.interrupted_work_items:
            self._state.interrupted_work_items.append(item_id)
            self.save()

    def clear_interrupted_work_items(self) -> None:
        """Clear interrupted work items list."""
        self._state.interrupted_work_items = []
        self.save()

    def request_shutdown(self, reason: str) -> None:
        """Request graceful shutdown.

        Args:
            reason: Reason for shutdown.
        """
        self._state.shutdown_requested = True
        self._state.shutdown_reason = reason
        self._state.status = PipelineStatus.STOPPING
        self.save()

    def clear_shutdown_request(self) -> None:
        """Clear shutdown request for resume."""
        self._state.shutdown_requested = False
        self._state.shutdown_reason = None
        self.save()

    def set_rejection_feedback(self, feedback: Optional[str]) -> None:
        """Set rejection feedback for retry with user guidance.

        Args:
            feedback: User's feedback on why they rejected the output.
        """
        self._state.rejection_feedback = feedback
        self.save()

    def get_rejection_feedback(self) -> Optional[str]:
        """Get rejection feedback if any.

        Returns:
            User's feedback or None.
        """
        return self._state.rejection_feedback

    def clear_rejection_feedback(self) -> None:
        """Clear rejection feedback after successful phase completion."""
        self._state.rejection_feedback = None
        self.save()
