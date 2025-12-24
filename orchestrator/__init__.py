"""Orchestrator module for the Autonomous Orchestrator Framework."""

from orchestrator.aggregator import (
    Aggregator,
    AggregationResult,
    AggregationStrategy,
    BestOfAggregator,
    ConcatenateAggregator,
    MergeAggregator,
    SynthesizeAggregator,
    VoteAggregator,
    create_aggregator,
)
from orchestrator.error_recovery import (
    ErrorCategory,
    ErrorEvent,
    ErrorPattern,
    ErrorRecoveryManager,
    RecoveryAction,
    RecoveryDecision,
    StuckDetectionResult,
    create_recovery_manager_from_config,
)
from orchestrator.heartbeat import HeartbeatManager
from orchestrator.phase_runner import PhaseRunner, create_default_runner
from orchestrator.resume import ResumeManager, ResumePoint
from orchestrator.shutdown import GracefulShutdown
from orchestrator.state_machine import (
    AgentSnapshot,
    PhaseState,
    PhaseStatus,
    PipelineState,
    PipelineStatus,
    StateMachine,
)
from orchestrator.swarm_controller import (
    AgentStatus,
    SwarmAgentConfig,
    SwarmAgentResult,
    SwarmController,
    SwarmResult,
    create_architecture_swarm_configs,
    create_ideation_swarm_configs,
)

__all__ = [
    # State Machine
    "StateMachine",
    "PipelineState",
    "PhaseState",
    "AgentSnapshot",
    "PipelineStatus",
    "PhaseStatus",
    # Phase Runner
    "PhaseRunner",
    "create_default_runner",
    # Shutdown
    "GracefulShutdown",
    # Resume
    "ResumeManager",
    "ResumePoint",
    # Heartbeat
    "HeartbeatManager",
    # Swarm Controller
    "SwarmController",
    "SwarmAgentConfig",
    "SwarmAgentResult",
    "SwarmResult",
    "AgentStatus",
    "create_ideation_swarm_configs",
    "create_architecture_swarm_configs",
    # Aggregator
    "Aggregator",
    "AggregationResult",
    "AggregationStrategy",
    "ConcatenateAggregator",
    "MergeAggregator",
    "SynthesizeAggregator",
    "VoteAggregator",
    "BestOfAggregator",
    "create_aggregator",
    # Error Recovery
    "ErrorRecoveryManager",
    "ErrorCategory",
    "ErrorEvent",
    "ErrorPattern",
    "RecoveryAction",
    "RecoveryDecision",
    "StuckDetectionResult",
    "create_recovery_manager_from_config",
]
