"""Swarm controller for parallel agent execution."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class AgentStatus(str, Enum):
    """Status of a swarm agent."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SwarmAgentConfig:
    """Configuration for a single swarm agent."""

    agent_id: str
    prompt: str
    role: str  # e.g., "user_requirements", "technical", "edge_cases"
    model: str = "claude-opus-4-5-20251101"
    timeout_seconds: int = 3600  # 1 hour default


@dataclass
class SwarmAgentResult:
    """Result from a single swarm agent."""

    agent_id: str
    role: str
    status: AgentStatus
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get the duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class SwarmResult:
    """Combined result from all swarm agents."""

    swarm_id: str
    agent_results: list[SwarmAgentResult]
    aggregated_output: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def all_succeeded(self) -> bool:
        """Check if all agents succeeded."""
        return all(r.status == AgentStatus.COMPLETED for r in self.agent_results)

    @property
    def any_succeeded(self) -> bool:
        """Check if any agent succeeded."""
        return any(r.status == AgentStatus.COMPLETED for r in self.agent_results)

    @property
    def success_count(self) -> int:
        """Count of successful agents."""
        return sum(1 for r in self.agent_results if r.status == AgentStatus.COMPLETED)

    @property
    def failure_count(self) -> int:
        """Count of failed agents."""
        return sum(1 for r in self.agent_results if r.status == AgentStatus.FAILED)

    @property
    def successful_outputs(self) -> list[str]:
        """Get outputs from successful agents."""
        return [
            r.output for r in self.agent_results
            if r.status == AgentStatus.COMPLETED and r.output
        ]


# Type alias for agent runner function
AgentRunner = Callable[[SwarmAgentConfig, Path], "asyncio.Future[SwarmAgentResult]"]


class SwarmController:
    """Controller for running multiple agents in parallel.

    This class manages the execution of multiple agents concurrently,
    typically used for planning phases like ideation and architecture
    where different perspectives are valuable.

    Example usage:
        controller = SwarmController()

        configs = [
            SwarmAgentConfig(
                agent_id="agent_1",
                prompt="Focus on user requirements...",
                role="user_requirements",
            ),
            SwarmAgentConfig(
                agent_id="agent_2",
                prompt="Focus on technical feasibility...",
                role="technical",
            ),
        ]

        result = await controller.run_swarm(configs, project_dir)

    With HTTP MCP servers (safe for concurrent access):
        controller = SwarmController(
            http_mcp_servers={
                "archon": {"type": "http", "url": "http://localhost:8000/mcp"}
            },
            mcp_tools=["mcp__archon__search_docs", "mcp__archon__get_context"]
        )
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        require_all_success: bool = False,
        min_success_count: int = 1,
        stagger_delay_seconds: float = 1.0,
        http_mcp_servers: Optional[dict[str, dict]] = None,
        mcp_tools: Optional[list[str]] = None,
    ) -> None:
        """Initialize the swarm controller.

        Args:
            max_concurrent: Maximum number of agents to run concurrently.
            require_all_success: If True, swarm fails if any agent fails.
            min_success_count: Minimum number of agents that must succeed.
            stagger_delay_seconds: Delay between starting each agent to reduce
                API initialization contention and "Control request timeout" errors.
            http_mcp_servers: HTTP/SSE MCP servers to include for swarm agents.
                Only type="http" or type="sse" servers are allowed (safe for concurrent access).
                stdio servers (command+args) will cause timeout errors with concurrent agents.
            mcp_tools: List of MCP tool names to allow (e.g., ["mcp__archon__search_docs"]).
        """
        self._max_concurrent = max_concurrent
        self._require_all_success = require_all_success
        self._min_success_count = min_success_count
        self._stagger_delay = stagger_delay_seconds
        self._http_mcp_servers = http_mcp_servers or {}
        self._mcp_tools = mcp_tools or []
        self._running_agents: dict[str, asyncio.Task] = {}
        self._shutdown_requested = False

    async def run_swarm(
        self,
        agents: list[SwarmAgentConfig],
        project_dir: Path,
        agent_runner: Optional[AgentRunner] = None,
        progress_callback: Optional[Callable[[str, AgentStatus], None]] = None,
    ) -> SwarmResult:
        """Run multiple agents in parallel.

        Args:
            agents: List of agent configurations.
            project_dir: Project directory for agents to work in.
            agent_runner: Optional custom agent runner function.
            progress_callback: Optional callback for progress updates.

        Returns:
            SwarmResult with all agent outputs.
        """
        swarm_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()
        results: list[SwarmAgentResult] = []

        # Use default runner if none provided
        runner = agent_runner or self._default_agent_runner

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def run_with_semaphore(config: SwarmAgentConfig, agent_index: int) -> SwarmAgentResult:
            """Run a single agent with semaphore limiting and staggered start.

            Args:
                config: Agent configuration.
                agent_index: Index of this agent (0-based) for stagger delay.
            """
            # Stagger agent initialization to avoid MCP server race conditions
            # (e.g., multiple npx puppeteer-mcp-server processes competing for resources)
            if agent_index > 0 and self._stagger_delay > 0:
                await asyncio.sleep(agent_index * self._stagger_delay)

            async with semaphore:
                if self._shutdown_requested:
                    return SwarmAgentResult(
                        agent_id=config.agent_id,
                        role=config.role,
                        status=AgentStatus.CANCELLED,
                        error="Shutdown requested",
                    )

                if progress_callback:
                    progress_callback(config.agent_id, AgentStatus.RUNNING)

                try:
                    result = await asyncio.wait_for(
                        runner(config, project_dir),
                        timeout=config.timeout_seconds,
                    )
                    if progress_callback:
                        progress_callback(config.agent_id, result.status)
                    return result

                except asyncio.TimeoutError:
                    result = SwarmAgentResult(
                        agent_id=config.agent_id,
                        role=config.role,
                        status=AgentStatus.FAILED,
                        error=f"Agent timed out after {config.timeout_seconds} seconds",
                    )
                    if progress_callback:
                        progress_callback(config.agent_id, AgentStatus.FAILED)
                    return result

                except Exception as e:
                    result = SwarmAgentResult(
                        agent_id=config.agent_id,
                        role=config.role,
                        status=AgentStatus.FAILED,
                        error=str(e),
                    )
                    if progress_callback:
                        progress_callback(config.agent_id, AgentStatus.FAILED)
                    return result

        # Create tasks for all agents (with staggered starts via agent_index)
        tasks = [
            asyncio.create_task(run_with_semaphore(config, idx), name=f"agent_{config.agent_id}")
            for idx, config in enumerate(agents)
        ]

        # Store running tasks for potential cancellation
        for config, task in zip(agents, tasks):
            self._running_agents[config.agent_id] = task

        # Wait for all tasks to complete
        try:
            results = await asyncio.gather(*tasks, return_exceptions=False)
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait for cancelled tasks to finish cleanup
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        except Exception as e:
            # Handle any unexpected errors
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait for cancelled tasks to finish cleanup
            await asyncio.gather(*tasks, return_exceptions=True)
            raise RuntimeError(f"Swarm execution failed: {e}") from e
        finally:
            # Clean up running agents tracking
            for config in agents:
                self._running_agents.pop(config.agent_id, None)

        completed_at = datetime.utcnow()

        return SwarmResult(
            swarm_id=swarm_id,
            agent_results=list(results),
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "total_agents": len(agents),
                "max_concurrent": self._max_concurrent,
            },
        )

    async def _default_agent_runner(
        self,
        config: SwarmAgentConfig,
        project_dir: Path,
    ) -> SwarmAgentResult:
        """Default agent runner using Claude SDK.

        Args:
            config: Agent configuration.
            project_dir: Project directory.

        Returns:
            SwarmAgentResult from the agent.
        """
        from agents.client import create_minimal_client

        started_at = datetime.utcnow()

        # Retry logic for transient initialization errors
        max_retries = 3
        retry_delay = 2.0  # seconds
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                # Use minimal client for swarm agents - only HTTP MCP servers allowed
                # This avoids "Control request timeout: initialize" errors from
                # concurrent stdio MCP server initialization (e.g., npx puppeteer-mcp-server)
                # HTTP MCP servers (like Archon) are safe for concurrent access
                client = create_minimal_client(
                    project_dir,
                    config.model,
                    verbose=False,
                    http_mcp_servers=self._http_mcp_servers,
                    allowed_tools=self._mcp_tools,
                )

                async with client:
                    await client.query(config.prompt)

                    response_text = ""
                    async for msg in client.receive_response():
                        msg_type = type(msg).__name__
                        if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                            for block in msg.content:
                                if hasattr(block, "text"):
                                    response_text += block.text

                return SwarmAgentResult(
                    agent_id=config.agent_id,
                    role=config.role,
                    status=AgentStatus.COMPLETED,
                    output=response_text,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    metadata={"attempts": attempt + 1},
                )

            except asyncio.CancelledError:
                # Handle cancellation - return cancelled status, don't re-raise
                return SwarmAgentResult(
                    agent_id=config.agent_id,
                    role=config.role,
                    status=AgentStatus.CANCELLED,
                    error="Agent cancelled",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            except Exception as e:
                error_str = str(e)
                last_error = error_str

                # Check if this is a transient error worth retrying
                is_transient = any(pattern in error_str.lower() for pattern in [
                    "control request timeout",
                    "connection reset",
                    "connection refused",
                    "temporary failure",
                    "timed out",
                ])

                if is_transient and attempt < max_retries - 1:
                    # Wait before retry with exponential backoff
                    wait_time = retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue

                # Non-transient error or max retries reached
                break

        return SwarmAgentResult(
            agent_id=config.agent_id,
            role=config.role,
            status=AgentStatus.FAILED,
            error=last_error,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            metadata={"attempts": max_retries},
        )

    async def cancel_agent(self, agent_id: str) -> bool:
        """Cancel a running agent.

        Args:
            agent_id: ID of the agent to cancel.

        Returns:
            True if agent was cancelled, False if not found.
        """
        task = self._running_agents.get(agent_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def cancel_all(self) -> int:
        """Cancel all running agents.

        Returns:
            Number of agents cancelled.
        """
        self._shutdown_requested = True
        cancelled = 0
        for agent_id, task in list(self._running_agents.items()):
            if not task.done():
                task.cancel()
                cancelled += 1
        return cancelled

    def check_should_stop(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_requested

    @property
    def running_agent_count(self) -> int:
        """Get count of currently running agents."""
        return sum(1 for task in self._running_agents.values() if not task.done())


def create_ideation_swarm_configs(
    idea: str,
    model: str = "claude-opus-4-5-20251101",
    rejection_feedback: Optional[str] = None,
) -> list[SwarmAgentConfig]:
    """Create swarm configs for ideation phase.

    Creates 3 specialized agents:
    - Agent 1: Focus on user requirements & use cases
    - Agent 2: Focus on technical feasibility & constraints
    - Agent 3: Focus on edge cases & potential issues

    Args:
        idea: The initial idea to brainstorm on.
        model: Model to use for agents.
        rejection_feedback: Optional feedback from user about why they rejected
            the previous iteration. This should be incorporated into the analysis.

    Returns:
        List of 3 SwarmAgentConfig objects.
    """
    # Build feedback section if provided
    feedback_section = ""
    if rejection_feedback:
        feedback_section = f"""
## IMPORTANT: User Feedback from Previous Iteration
The user reviewed a previous version of this analysis and provided the following feedback.
**You MUST incorporate this feedback into your analysis:**

> {rejection_feedback}

Please ensure your analysis addresses this feedback directly.
"""

    return [
        SwarmAgentConfig(
            agent_id=f"ideation_user_{uuid.uuid4().hex[:6]}",
            role="user_requirements",
            model=model,
            prompt=f"""# Ideation: User Requirements Analysis

## Your Role
You are a user experience and product requirements specialist. Your focus is on understanding user needs, defining user stories, and ensuring the product meets user expectations.

## The Idea
{idea}
{feedback_section}
## Your Task
Analyze this idea from a user-centric perspective:

1. **User Personas**: Define 2-3 key user personas who would use this product
2. **User Stories**: Write detailed user stories in the format "As a [persona], I want to [action] so that [benefit]"
3. **User Journeys**: Map out the main user workflows
4. **Feature Priority**: Categorize features as MVP (must-have), Nice-to-have, and Future
5. **Usability Requirements**: Define usability and accessibility needs

Output your analysis in a structured Markdown format.""",
        ),
        SwarmAgentConfig(
            agent_id=f"ideation_tech_{uuid.uuid4().hex[:6]}",
            role="technical_feasibility",
            model=model,
            prompt=f"""# Ideation: Technical Feasibility Analysis

## Your Role
You are a technical architect and feasibility specialist. Your focus is on evaluating technical requirements, constraints, and implementation considerations.

## The Idea
{idea}
{feedback_section}
## Your Task
Analyze this idea from a technical perspective:

1. **Data Model**: What data needs to be stored? Define key entities and relationships
2. **Architecture Options**: Suggest 2-3 architectural approaches (monolith, microservices, serverless, etc.)
3. **Technology Stack**: Recommend technologies for frontend, backend, database, etc.
4. **Integrations**: What external services or APIs might be needed?
5. **Performance Requirements**: Define performance expectations (latency, throughput, etc.)
6. **Security Considerations**: Identify security requirements and potential vulnerabilities
7. **Scalability**: How should the system scale?

Output your analysis in a structured Markdown format.""",
        ),
        SwarmAgentConfig(
            agent_id=f"ideation_edge_{uuid.uuid4().hex[:6]}",
            role="edge_cases",
            model=model,
            prompt=f"""# Ideation: Edge Cases & Risk Analysis

## Your Role
You are a quality assurance and risk analysis specialist. Your focus is on identifying potential issues, edge cases, and failure scenarios.

## The Idea
{idea}
{feedback_section}
## Your Task
Analyze this idea for potential problems:

1. **Edge Cases**: What unusual scenarios could break the system?
2. **Error Scenarios**: What could go wrong? How should errors be handled?
3. **Data Edge Cases**: What about empty data, null values, large datasets?
4. **Concurrency Issues**: What happens with multiple simultaneous users/operations?
5. **Failure Modes**: How should the system behave when dependencies fail?
6. **Security Risks**: What are potential attack vectors?
7. **Compliance**: Are there regulatory or legal considerations?
8. **Testing Strategy**: How should this system be tested?

Output your analysis in a structured Markdown format.""",
        ),
    ]


def create_architecture_swarm_configs(
    requirements: str,
    model: str = "claude-opus-4-5-20251101",
) -> list[SwarmAgentConfig]:
    """Create swarm configs for architecture phase.

    Creates 3 specialized agents:
    - Agent 1: Focus on system design & component architecture
    - Agent 2: Focus on data modeling & database design
    - Agent 3: Focus on API design & integration patterns

    Args:
        requirements: The requirements document from ideation phase.
        model: Model to use for agents.

    Returns:
        List of 3 SwarmAgentConfig objects.
    """
    return [
        SwarmAgentConfig(
            agent_id=f"arch_system_{uuid.uuid4().hex[:6]}",
            role="system_design",
            model=model,
            prompt=f"""# Architecture: System Design

## Your Role
You are a system architect focusing on high-level system design and component architecture.

## Requirements
{requirements}

## Your Task
Design the system architecture:

1. **System Overview**: High-level architecture diagram (describe in text)
2. **Components**: Define main system components and their responsibilities
3. **Communication**: How do components communicate? (REST, gRPC, message queues, etc.)
4. **Deployment**: Deployment architecture (containers, serverless, VMs)
5. **Infrastructure**: Required infrastructure components (load balancers, caches, CDN)
6. **Technology Choices**: Specific technology recommendations with rationale

Output your design in a structured Markdown format.""",
        ),
        SwarmAgentConfig(
            agent_id=f"arch_data_{uuid.uuid4().hex[:6]}",
            role="data_models",
            model=model,
            prompt=f"""# Architecture: Data Modeling

## Your Role
You are a data architect focusing on data modeling and database design.

## Requirements
{requirements}

## Your Task
Design the data layer:

1. **Entity Relationship**: Define all entities and their relationships
2. **Database Choice**: Recommend database type(s) with rationale (SQL, NoSQL, graph, etc.)
3. **Schema Design**: Detailed schema definitions (tables/collections, fields, indexes)
4. **Data Flow**: How does data flow through the system?
5. **Caching Strategy**: What data should be cached and how?
6. **Migration Strategy**: How to handle schema changes over time

Output your design in a structured Markdown format with actual schema definitions.""",
        ),
        SwarmAgentConfig(
            agent_id=f"arch_api_{uuid.uuid4().hex[:6]}",
            role="api_design",
            model=model,
            prompt=f"""# Architecture: API Design

## Your Role
You are an API architect focusing on API design and integration patterns.

## Requirements
{requirements}

## Your Task
Design the API layer:

1. **API Style**: REST, GraphQL, gRPC - with rationale
2. **Endpoint Design**: Define main API endpoints/operations
3. **Authentication**: Auth strategy (JWT, OAuth, API keys)
4. **Authorization**: Permission model and access control
5. **Rate Limiting**: Rate limiting strategy
6. **Versioning**: API versioning approach
7. **Error Handling**: Standardized error responses
8. **Documentation**: OpenAPI/Swagger spec outline

Output your design in a structured Markdown format with actual endpoint definitions.""",
        ),
    ]
