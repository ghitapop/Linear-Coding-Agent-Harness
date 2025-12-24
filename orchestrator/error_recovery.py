"""Error recovery for the Autonomous Orchestrator Framework.

Provides smart retry with context injection, stuck detection, and
escalation after repeated failures.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


class ErrorCategory(str, Enum):
    """Categories of errors for targeted recovery."""

    RATE_LIMIT = "rate_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    BLOCKED_COMMAND = "blocked_command"
    TOOL_FAILURE = "tool_failure"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_NOT_FOUND = "resource_not_found"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    """Actions to take for recovery."""

    RETRY_IMMEDIATELY = "retry_immediately"
    RETRY_WITH_DELAY = "retry_with_delay"
    RETRY_WITH_HINT = "retry_with_hint"
    REDUCE_CONTEXT = "reduce_context"
    ESCALATE_TO_USER = "escalate_to_user"
    SKIP_AND_CONTINUE = "skip_and_continue"
    ABORT = "abort"


@dataclass
class ErrorPattern:
    """Pattern for matching and categorizing errors."""

    category: ErrorCategory
    patterns: list[str]  # Regex patterns
    recovery_action: RecoveryAction
    retry_delay_seconds: int = 0
    hint_template: Optional[str] = None


@dataclass
class ErrorEvent:
    """Record of a single error occurrence."""

    timestamp: datetime
    category: ErrorCategory
    message: str
    phase: Optional[str] = None
    work_item_id: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryDecision:
    """Decision about how to recover from an error."""

    action: RecoveryAction
    hint: Optional[str] = None
    retry_delay_seconds: int = 0
    should_escalate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StuckDetectionResult:
    """Result of stuck detection check."""

    is_stuck: bool
    reason: Optional[str] = None
    stuck_duration_minutes: float = 0.0
    repeated_error_count: int = 0
    recommendation: Optional[RecoveryAction] = None


# Default error patterns with recovery strategies
DEFAULT_ERROR_PATTERNS = [
    # Rate limit errors
    ErrorPattern(
        category=ErrorCategory.RATE_LIMIT,
        patterns=[
            r"rate.?limit",
            r"too.?many.?requests",
            r"429",
            r"quota.?exceeded",
            r"throttl",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_DELAY,
        retry_delay_seconds=60,
        hint_template="Rate limit encountered. Waiting {delay} seconds before retry.",
    ),

    # Context overflow
    ErrorPattern(
        category=ErrorCategory.CONTEXT_OVERFLOW,
        patterns=[
            r"context.?(length|window|limit)",
            r"token.?limit",
            r"maximum.?context",
            r"too.?long",
            r"truncat",
        ],
        recovery_action=RecoveryAction.REDUCE_CONTEXT,
        hint_template="""Context limit reached. Try these approaches:
1. Focus on one specific sub-task at a time
2. Summarize previous work instead of including full history
3. Work with smaller files or file sections""",
    ),

    # Blocked commands
    ErrorPattern(
        category=ErrorCategory.BLOCKED_COMMAND,
        patterns=[
            r"command.?not.?allowed",
            r"blocked.?by.?security",
            r"security.?hook",
            r"permission.?denied.*bash",
            r"allowlist",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_HINT,
        hint_template="""The command was blocked by security rules. Alternatives:
1. Use an allowed command from the allowlist
2. Break down the operation into simpler steps
3. Use the built-in file tools instead of bash commands
4. Ask the user for permission if the operation is essential""",
    ),

    # Tool failures
    ErrorPattern(
        category=ErrorCategory.TOOL_FAILURE,
        patterns=[
            r"tool.?(call|use).?fail",
            r"failed.?to.?(execute|run)",
            r"error.?executing",
            r"subprocess.?error",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_HINT,
        hint_template="""Tool execution failed. Consider:
1. Check if the tool input is correctly formatted
2. Verify file paths exist and are accessible
3. Try an alternative approach to accomplish the same goal""",
    ),

    # Network errors
    ErrorPattern(
        category=ErrorCategory.NETWORK_ERROR,
        patterns=[
            r"network.?error",
            r"connection.?(refused|reset|timeout)",
            r"dns.?resolution",
            r"unreachable",
            r"ECONNREFUSED",
            r"ETIMEDOUT",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_DELAY,
        retry_delay_seconds=10,
        hint_template="Network error encountered. Retrying after brief delay.",
    ),

    # Timeout
    ErrorPattern(
        category=ErrorCategory.TIMEOUT,
        patterns=[
            r"timeout",
            r"timed.?out",
            r"deadline.?exceeded",
            r"took.?too.?long",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_HINT,
        retry_delay_seconds=5,
        hint_template="""Operation timed out. Suggestions:
1. Break the operation into smaller chunks
2. Process fewer items at a time
3. Skip resource-intensive validations temporarily""",
    ),

    # Permission denied
    ErrorPattern(
        category=ErrorCategory.PERMISSION_DENIED,
        patterns=[
            r"permission.?denied",
            r"access.?denied",
            r"unauthorized",
            r"forbidden",
            r"403",
        ],
        recovery_action=RecoveryAction.ESCALATE_TO_USER,
        hint_template="Permission denied. User intervention may be required.",
    ),

    # Resource not found
    ErrorPattern(
        category=ErrorCategory.RESOURCE_NOT_FOUND,
        patterns=[
            r"not.?found",
            r"does.?not.?exist",
            r"no.?such.?file",
            r"404",
            r"missing.?resource",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_HINT,
        hint_template="""Resource not found. Check:
1. Verify the file/resource path is correct
2. Ensure the resource has been created before accessing it
3. Check for typos in the path or identifier""",
    ),

    # Validation errors
    ErrorPattern(
        category=ErrorCategory.VALIDATION_ERROR,
        patterns=[
            r"validation.?(error|fail)",
            r"invalid.?(input|format|value)",
            r"schema.?error",
            r"type.?error",
        ],
        recovery_action=RecoveryAction.RETRY_WITH_HINT,
        hint_template="""Validation error. Suggestions:
1. Review the expected format or schema
2. Check for missing required fields
3. Ensure data types match expectations""",
    ),
]


class ErrorRecoveryManager:
    """Manages error detection, categorization, and recovery.

    This class provides:
    - Error categorization using pattern matching
    - Stuck detection (repeated errors, no progress)
    - Smart retry with context injection
    - Escalation after max retries

    Example usage:
        manager = ErrorRecoveryManager()

        # Record an error
        manager.record_error("rate limit exceeded", phase="implement")

        # Get recovery decision
        decision = manager.get_recovery_decision("rate limit exceeded")
        if decision.action == RecoveryAction.RETRY_WITH_DELAY:
            await asyncio.sleep(decision.retry_delay_seconds)
            # retry...
    """

    def __init__(
        self,
        max_consecutive_errors: int = 3,
        stall_timeout_minutes: int = 30,
        max_total_retries: int = 10,
        error_patterns: Optional[list[ErrorPattern]] = None,
    ) -> None:
        """Initialize the error recovery manager.

        Args:
            max_consecutive_errors: Max same error before escalation.
            stall_timeout_minutes: Minutes without progress = stalled.
            max_total_retries: Max total retries before abort.
            error_patterns: Custom error patterns (uses defaults if None).
        """
        self._max_consecutive = max_consecutive_errors
        self._stall_timeout = timedelta(minutes=stall_timeout_minutes)
        self._max_total_retries = max_total_retries
        self._patterns = error_patterns or DEFAULT_ERROR_PATTERNS

        # Error history
        self._error_history: list[ErrorEvent] = []
        self._last_progress: datetime = datetime.utcnow()
        self._total_retries: int = 0

        # Callbacks
        self._escalation_callback: Optional[Callable[[str, ErrorEvent], None]] = None

    def set_escalation_callback(
        self,
        callback: Callable[[str, ErrorEvent], None],
    ) -> None:
        """Set callback for escalation events.

        Args:
            callback: Function(reason, error_event) to call on escalation.
        """
        self._escalation_callback = callback

    def categorize_error(self, error_message: str) -> ErrorCategory:
        """Categorize an error message.

        Args:
            error_message: The error message to categorize.

        Returns:
            ErrorCategory for the error.
        """
        message_lower = error_message.lower()

        for pattern in self._patterns:
            for regex in pattern.patterns:
                if re.search(regex, message_lower, re.IGNORECASE):
                    return pattern.category

        return ErrorCategory.UNKNOWN

    def record_error(
        self,
        error_message: str,
        phase: Optional[str] = None,
        work_item_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """Record an error occurrence.

        Args:
            error_message: The error message.
            phase: Optional phase where error occurred.
            work_item_id: Optional work item being processed.
            context: Optional additional context.

        Returns:
            The recorded ErrorEvent.
        """
        category = self.categorize_error(error_message)

        event = ErrorEvent(
            timestamp=datetime.utcnow(),
            category=category,
            message=error_message,
            phase=phase,
            work_item_id=work_item_id,
            context=context or {},
        )

        self._error_history.append(event)
        self._total_retries += 1

        return event

    def record_progress(self) -> None:
        """Record that progress was made (resets stall detection)."""
        self._last_progress = datetime.utcnow()

    def get_recovery_decision(
        self,
        error_message: str,
        phase: Optional[str] = None,
    ) -> RecoveryDecision:
        """Get recovery decision for an error.

        Args:
            error_message: The error message.
            phase: Optional phase context.

        Returns:
            RecoveryDecision with action and hints.
        """
        category = self.categorize_error(error_message)

        # Check total retries
        if self._total_retries >= self._max_total_retries:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                should_escalate=True,
                metadata={
                    "reason": "max_total_retries_exceeded",
                    "total_retries": self._total_retries,
                },
            )

        # Check for stuck condition
        stuck = self.check_if_stuck()
        if stuck.is_stuck:
            return RecoveryDecision(
                action=RecoveryAction.ESCALATE_TO_USER,
                hint=f"Agent appears stuck: {stuck.reason}",
                should_escalate=True,
                metadata={
                    "stuck_reason": stuck.reason,
                    "stuck_duration_minutes": stuck.stuck_duration_minutes,
                },
            )

        # Find matching pattern
        pattern = self._find_pattern(category)

        if pattern:
            hint = None
            if pattern.hint_template:
                hint = pattern.hint_template.format(
                    delay=pattern.retry_delay_seconds,
                    error=error_message,
                )

            return RecoveryDecision(
                action=pattern.recovery_action,
                hint=hint,
                retry_delay_seconds=pattern.retry_delay_seconds,
                metadata={"category": category.value},
            )

        # Default: retry with generic hint
        return RecoveryDecision(
            action=RecoveryAction.RETRY_WITH_HINT,
            hint=self._get_generic_hint(error_message),
            metadata={"category": "unknown"},
        )

    def check_if_stuck(self) -> StuckDetectionResult:
        """Check if the agent appears to be stuck.

        Stuck conditions:
        - Same error repeated N times consecutively
        - No progress for stall_timeout duration

        Returns:
            StuckDetectionResult with detection details.
        """
        now = datetime.utcnow()

        # Check for stall timeout
        time_since_progress = now - self._last_progress
        if time_since_progress > self._stall_timeout:
            return StuckDetectionResult(
                is_stuck=True,
                reason=f"No progress for {time_since_progress.total_seconds() / 60:.1f} minutes",
                stuck_duration_minutes=time_since_progress.total_seconds() / 60,
                recommendation=RecoveryAction.ESCALATE_TO_USER,
            )

        # Check for repeated same error
        if len(self._error_history) >= self._max_consecutive:
            recent = self._error_history[-self._max_consecutive:]
            categories = [e.category for e in recent]

            if len(set(categories)) == 1 and categories[0] != ErrorCategory.UNKNOWN:
                return StuckDetectionResult(
                    is_stuck=True,
                    reason=f"Same error ({categories[0].value}) repeated {self._max_consecutive} times",
                    repeated_error_count=self._max_consecutive,
                    recommendation=RecoveryAction.ESCALATE_TO_USER,
                )

            # Check for same error message (more specific)
            messages = [e.message for e in recent]
            if len(set(messages)) == 1:
                return StuckDetectionResult(
                    is_stuck=True,
                    reason=f"Identical error repeated {self._max_consecutive} times",
                    repeated_error_count=self._max_consecutive,
                    recommendation=RecoveryAction.ESCALATE_TO_USER,
                )

        return StuckDetectionResult(is_stuck=False)

    def _find_pattern(self, category: ErrorCategory) -> Optional[ErrorPattern]:
        """Find error pattern for a category.

        Args:
            category: Error category.

        Returns:
            ErrorPattern or None.
        """
        for pattern in self._patterns:
            if pattern.category == category:
                return pattern
        return None

    def _get_generic_hint(self, error_message: str) -> str:
        """Get a generic debugging hint.

        Args:
            error_message: The error message.

        Returns:
            Generic hint string.
        """
        return f"""An error occurred: {error_message}

Debugging suggestions:
1. Review the error message carefully for clues
2. Check if any assumptions about the environment are incorrect
3. Try a simpler approach first, then add complexity
4. Verify all file paths and resource identifiers
5. Consider breaking the task into smaller steps"""

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of error history.

        Returns:
            Summary dict with statistics.
        """
        if not self._error_history:
            return {
                "total_errors": 0,
                "categories": {},
                "last_error": None,
            }

        categories: dict[str, int] = {}
        for event in self._error_history:
            cat = event.category.value
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_errors": len(self._error_history),
            "total_retries": self._total_retries,
            "categories": categories,
            "last_error": {
                "message": self._error_history[-1].message,
                "category": self._error_history[-1].category.value,
                "timestamp": self._error_history[-1].timestamp.isoformat(),
            },
            "minutes_since_progress": (
                datetime.utcnow() - self._last_progress
            ).total_seconds() / 60,
        }

    def reset(self) -> None:
        """Reset error history and counters."""
        self._error_history = []
        self._last_progress = datetime.utcnow()
        self._total_retries = 0

    def inject_recovery_context(
        self,
        original_prompt: str,
        error_message: str,
        decision: RecoveryDecision,
    ) -> str:
        """Inject recovery context into a prompt for retry.

        Args:
            original_prompt: The original prompt.
            error_message: The error that occurred.
            decision: Recovery decision with hints.

        Returns:
            Modified prompt with recovery context.
        """
        recovery_context = f"""
## Recovery Context

Your previous attempt encountered an error:
```
{error_message}
```

{decision.hint or "Please try again with a different approach."}

Remember:
- Analyze what went wrong before attempting again
- Consider alternative approaches
- Start with simpler steps and build up
- If stuck, explicitly state what's blocking you

---

"""
        return recovery_context + original_prompt


def create_recovery_manager_from_config(
    config: Optional[dict[str, Any]] = None,
) -> ErrorRecoveryManager:
    """Create an ErrorRecoveryManager from configuration.

    Args:
        config: Optional configuration dict with keys:
            - max_consecutive_errors: int
            - stall_timeout_minutes: int
            - max_total_retries: int

    Returns:
        Configured ErrorRecoveryManager.
    """
    if config is None:
        return ErrorRecoveryManager()

    return ErrorRecoveryManager(
        max_consecutive_errors=config.get("max_consecutive_errors", 3),
        stall_timeout_minutes=config.get("stall_timeout_minutes", 30),
        max_total_retries=config.get("max_total_retries", 10),
    )
