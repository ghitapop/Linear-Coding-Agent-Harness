"""Phases module for the Autonomous Orchestrator Framework."""

from phases.base import Phase, PhaseConfig, PhaseResult, PhaseStatus, PlanningPattern
from phases.architecture import ArchitecturePhase
from phases.deploy import DeployPhase
from phases.ideation import IdeationPhase
from phases.implement import ImplementPhase
from phases.initialize import InitializePhase
from phases.task_breakdown import TaskBreakdownPhase
from phases.testing import TestingPhase

__all__ = [
    # Base classes and enums
    "Phase",
    "PhaseConfig",
    "PhaseResult",
    "PhaseStatus",
    "PlanningPattern",
    # Phase implementations (in pipeline order)
    "IdeationPhase",        # Phase 1: Idea → Requirements
    "ArchitecturePhase",    # Phase 2: Requirements → Architecture
    "TaskBreakdownPhase",   # Phase 3: Architecture → Tasks
    "InitializePhase",      # Phase 4: Project setup
    "ImplementPhase",       # Phase 5: Task implementation
    "TestingPhase",         # Phase 6: Comprehensive testing
    "DeployPhase",          # Phase 7: Deployment (optional)
    # Registry and utilities
    "PHASE_REGISTRY",
    "DEFAULT_PIPELINE",
    "get_phase_class",
    "create_phase",
]

# Phase registry for dynamic lookup
PHASE_REGISTRY: dict[str, type[Phase]] = {
    "ideation": IdeationPhase,
    "architecture": ArchitecturePhase,
    "task_breakdown": TaskBreakdownPhase,
    "initialize": InitializePhase,
    "implement": ImplementPhase,
    "testing": TestingPhase,
    "deploy": DeployPhase,
}

# Default pipeline order
DEFAULT_PIPELINE = [
    "ideation",
    "architecture",
    "task_breakdown",
    "initialize",
    "implement",
    "testing",
    "deploy",
]


def get_phase_class(name: str) -> type[Phase]:
    """Get a phase class by name.

    Args:
        name: The phase name.

    Returns:
        The phase class.

    Raises:
        KeyError: If phase not found.
    """
    if name not in PHASE_REGISTRY:
        raise KeyError(f"Unknown phase: {name}. Available: {list(PHASE_REGISTRY.keys())}")
    return PHASE_REGISTRY[name]


def create_phase(name: str, config: PhaseConfig | None = None) -> Phase:
    """Create a phase instance by name.

    Args:
        name: The phase name.
        config: Optional phase configuration.

    Returns:
        The phase instance.
    """
    phase_class = get_phase_class(name)
    return phase_class(config=config)
