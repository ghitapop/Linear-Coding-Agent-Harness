# Autonomous Orchestrator Framework - Implementation Plan

**Status:** MVP (Sprints 1-5) ✅ COMPLETED | Sprint 6 ✅ COMPLETED | Sprints 7-8 ✅ COMPLETED | Sprints 9-10 ✅ COMPLETED

## Goal
Build a "run until finished" orchestrator that autonomously develops complete software from idea to deployment, with configurable autonomy, pluggable backends, and Docker support.

## Requirements Summary
- **Full lifecycle**: Ideation → Architecture → Task Breakdown → Init → Implement → Test → Deploy
- **Configurable planning**: Swarm (3 parallel agents) or single agent per phase
- **Pluggable work tracking**: Abstract interface (Linear backend, JSON backend)
- **Two deployment modes**: Local (CLI chat) vs Docker (REST API only)
- **Multi-project manager**: Track multiple projects with history
- **PostgreSQL database**: Bundled with Docker or connect to external
- **Slash commands**: `/projects`, `/status`, `/resume`, `/stop`, `/help`
- **Auto-retry with hints**: Detect stuck agents, inject debugging context
- **Configurable autonomy**: Full auto vs checkpoint pauses
- **Docker-ready**: Containerized for deployment anywhere

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     main.py (Entry Point)                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              orchestrator/state_machine.py                   │
│  • Pipeline state persistence (.orchestrator_state.json)     │
│  • Phase transitions, resume capability                      │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│               orchestrator/phase_runner.py                   │
│  • Executes phases sequentially                              │
│  • Handles checkpoints, error recovery                       │
│  • Spawns swarms via swarm_controller.py                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
     ┌────────────────────────┼────────────────────────┐
     ▼                        ▼                        ▼
┌─────────┐            ┌─────────────┐          ┌──────────┐
│ Phase 1 │   ───►     │ Phase 2-7   │  ───►    │ Complete │
│Ideation │            │ (loop)      │          │          │
└─────────┘            └─────────────┘          └──────────┘
```

---

## Implementation Sprints

### Sprint 1: Foundation (Core Infrastructure)
Create base packages and interfaces.

**New Files:**
```
orchestrator/
├── __init__.py
├── state_machine.py      # PipelineState, PhaseState, persistence
├── phase_runner.py       # Main loop: run phases until complete
├── swarm_controller.py   # Parallel agent execution
├── aggregator.py         # Vote/merge swarm outputs
├── error_recovery.py     # Stuck detection, retry with hints
├── shutdown.py           # Graceful shutdown with state preservation
├── resume.py             # Resume from saved state
└── heartbeat.py          # Background heartbeat for crash detection

backends/
├── __init__.py
├── base.py               # WorkTracker abstract interface
├── json_backend.py       # Local JSON file backend
└── linear_backend.py     # Wraps existing Linear integration

config/
├── __init__.py
├── schema.py             # Pydantic config models
└── loader.py             # YAML config loading

main.py                   # New entry point
orchestrator.yaml         # Default config template

adapters/                 # NEW: Pluggable input/interaction
├── __init__.py
├── base.py               # Abstract InputAdapter interface
├── cli_adapter.py        # Interactive CLI with slash commands
└── api_adapter.py        # REST API for Docker deployment

database/                 # NEW: PostgreSQL persistence
├── __init__.py
├── models.py             # SQLAlchemy models (Project, WorkItem, etc.)
├── connection.py         # Database connection management
├── migrations/           # Alembic migrations
└── repository.py         # Data access layer

api/                      # NEW: REST API (FastAPI)
├── __init__.py
├── main.py               # FastAPI app
├── routes/
│   ├── projects.py       # /projects endpoints
│   └── health.py         # /health endpoint
└── schemas.py            # Pydantic request/response models
```

**Key Classes:**
- `PipelineState` - Persisted state with phase statuses
- `WorkTracker` - Abstract interface: `create_work_item()`, `get_next_work_item()`, `update_work_item()`
- `OrchestratorConfig` - Pydantic model for YAML config
- `InputAdapter` - Abstract interface for user interaction (CLI, API, etc.)

### Sprint 2: Phase System
Abstract phases and wrap existing agents.

**New Files:**
```
phases/
├── __init__.py
├── base.py               # Abstract Phase class
├── ideation.py           # Phase 1: Idea → Requirements
├── architecture.py       # Phase 2: Requirements → Tech Stack
├── task_breakdown.py     # Phase 3: Architecture → 200+ Features
├── initialize.py         # Phase 4: Wraps existing Initializer
├── implement.py          # Phase 5: Wraps existing Coding Agent
├── testing.py            # Phase 6: Comprehensive testing
└── deploy.py             # Phase 7: Optional deployment

prompts/
├── ideation/
│   ├── brainstorm.md
│   └── aggregate.md
├── architecture/
│   ├── system_design.md
│   ├── data_models.md
│   └── aggregate.md
├── task_breakdown/
│   └── decompose.md
├── testing/
│   └── test_plan.md
└── deploy/
    └── deploy.md
```

**Key Pattern - Wrap Existing Agents:**
```python
# phases/initialize.py
class InitializePhase(Phase):
    async def run(self, input_data, config, work_tracker, project_dir):
        prompt = get_initializer_prompt()  # Reuse existing
        client = create_client(project_dir, config.model)  # Reuse existing
        async with client:
            status, response = await run_agent_session(client, prompt, project_dir)
        return PhaseResult(status=..., output=response)
```

### Sprint 3: Swarm Support
Enable parallel agents for planning phases.

**Key Logic in `swarm_controller.py`:**
```python
async def run_swarm(agents: List[SwarmAgent]) -> Dict:
    # Run 3 agents in parallel
    tasks = [self._run_agent(a) for a in agents]
    results = await asyncio.gather(*tasks)
    # Aggregate via voting/merging
    return self.aggregator.aggregate(results)
```

**Ideation Swarm (3 agents):**
1. Agent 1: Focus on user requirements & use cases
2. Agent 2: Focus on technical feasibility & constraints
3. Agent 3: Focus on edge cases & potential issues

### Sprint 4: Error Recovery
Smart retry with context injection.

**`error_recovery.py` Key Features:**
- Detect stuck: Same error 3x or no progress 30min
- Pattern matching for common errors (rate limit, context overflow, blocked command)
- Inject debugging hints into retry prompt
- Escalate after N retries (pause for human if checkpoint mode)

### Sprint 5: Docker + PostgreSQL
Containerization with database.

**New Files:**
```
Dockerfile
docker-compose.yml
database/
├── migrations/
└── init.sql
```

**docker-compose.yml (with profiles):**
```yaml
services:
  # ============================================
  # EXTERNAL DATABASE (Supabase, Neon, etc.)
  # Command: docker-compose --profile external-db up
  # ============================================
  orchestrator:
    profiles: ["external-db"]
    build: .
    env_file: .env  # DATABASE_URL from .env
    ports:
      - "${API_PORT:-8080}:8080"
    volumes:
      - ${WORKSPACE_PATH:-./workspace}:/workspace
    restart: unless-stopped

  # ============================================
  # BUNDLED POSTGRESQL
  # Command: docker-compose --profile with-db up
  # ============================================
  orchestrator-with-db:
    profiles: ["with-db"]
    build: .
    env_file: .env
    environment:
      # Override DATABASE_URL to use Docker service name
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/orchestrator
    ports:
      - "${API_PORT:-8080}:8080"
    volumes:
      - ${WORKSPACE_PATH:-./workspace}:/workspace
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    profiles: ["with-db"]
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orchestrator
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/migrations:/docker-entrypoint-initdb.d
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Usage:**
```bash
# With bundled PostgreSQL
docker-compose --profile with-db up

# With external database (Supabase, Neon, etc.)
# Set DATABASE_URL in .env first
docker-compose --profile external-db up
```

**.env Example:**
```bash
# Required
CLAUDE_CODE_OAUTH_TOKEN=your-token
LINEAR_API_KEY=lin_api_xxx

# For external-db profile
DATABASE_URL=postgresql://user:pass@your-host:5432/orchestrator

# Optional
API_PORT=8080
WORKSPACE_PATH=./workspace
```

---

## Files to Modify (Existing)

| File | Changes |
|------|---------|
| `prompts.py` | Add `load_phase_prompt(phase, name)` function |
| `client.py` | Add optional `phase_context` parameter to `create_client()` |
| `progress.py` | Add multi-backend progress query support |
| `requirements.txt` | Add `pydantic`, `pyyaml` dependencies |

**No changes to:**
- `security.py` (security is critical - don't touch)
- `linear_config.py` (constants still valid)

---

## Pipeline State Machine

```
NOT_STARTED → RUNNING → COMPLETED
                ↓ ↑
              PAUSED (checkpoint)
                ↓
              FAILED (max retries)
                ↓
            STOPPING → STOPPED (graceful shutdown)
```

**Completion Detection:**
```python
def is_complete(state: PipelineState) -> bool:
    return all(
        p.status in [PhaseStatus.COMPLETED, PhaseStatus.SKIPPED]
        for p in state.phases.values()
    )
```

---

## Graceful Shutdown & State Persistence

### Design Principles
1. **Never lose work** - State saved continuously, not just on exit
2. **Atomic saves** - Write to temp file, then rename (no corruption)
3. **Agent snapshots** - Capture agent state before termination
4. **Idempotent resume** - Safe to restart at any point
5. **Signal handling** - Catch all termination signals gracefully

### Shutdown Flow
```
┌─────────────────────────────────────────────────────────────────┐
│  User presses CTRL+C or sends SIGTERM                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Set STOPPING flag (prevents new work from starting)         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Signal running agents to finish current atomic unit         │
│     (don't interrupt mid-file-write or mid-tool-call)           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Capture agent snapshots:                                    │
│     - Current phase & step                                      │
│     - Last successful tool call                                 │
│     - Pending work item                                         │
│     - Agent conversation context (truncated)                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Save state atomically:                                      │
│     - Write to .orchestrator_state.json.tmp                     │
│     - Verify JSON is valid                                      │
│     - Rename to .orchestrator_state.json                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Update work tracker (mark in-progress items as interrupted) │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Exit cleanly with status code 0                             │
└─────────────────────────────────────────────────────────────────┘
```

### Continuous Checkpointing
State is saved automatically at these points (not just shutdown):

| Event | What's Saved |
|-------|--------------|
| Phase starts | Phase status → RUNNING |
| Phase completes | Phase status → COMPLETED, output reference |
| Work item claimed | Item status → IN_PROGRESS |
| Work item done | Item status → DONE, implementation notes |
| Agent session ends | Session summary, last progress |
| Every 60 seconds | Heartbeat timestamp (detect crashes) |
| On any error | Error details, retry count |

### State File Structure
```python
# .orchestrator_state.json
@dataclass
class PipelineState:
    # Core state
    project_id: str
    status: PipelineStatus
    current_phase: str
    phases: Dict[str, PhaseState]

    # Shutdown/Resume support
    last_checkpoint: datetime          # When state was last saved
    heartbeat: datetime                # Updated every 60s (detect crashes)
    shutdown_requested: bool           # Graceful shutdown in progress
    shutdown_reason: Optional[str]     # "user_request", "error", "budget"

    # Agent snapshots (for resume)
    agent_snapshots: List[AgentSnapshot]

    # Recovery info
    interrupted_work_items: List[str]  # Items that were in-progress
    last_successful_step: str          # Where to resume from


@dataclass
class AgentSnapshot:
    agent_id: str
    phase: str
    started_at: datetime
    last_activity: datetime
    current_work_item: Optional[str]
    last_tool_call: Optional[str]
    conversation_summary: str          # Brief summary for context
    can_resume: bool                   # Whether this agent can be resumed
```

### Signal Handling
```python
# orchestrator/shutdown.py

import signal
import asyncio
from typing import Optional

class GracefulShutdown:
    """Handles graceful shutdown with state preservation."""

    def __init__(self, state_machine: StateMachine, work_tracker: WorkTracker):
        self.state_machine = state_machine
        self.work_tracker = work_tracker
        self.shutdown_requested = False
        self.running_agents: List[AgentHandle] = []

    def install_handlers(self):
        """Install signal handlers for graceful shutdown."""
        # CTRL+C
        signal.signal(signal.SIGINT, self._handle_signal)
        # kill command
        signal.signal(signal.SIGTERM, self._handle_signal)
        # Windows console close
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle termination signal."""
        print(f"\n⚠️  Shutdown requested (signal {signum})")
        print("Saving state and stopping gracefully...")
        self.shutdown_requested = True

        # Create async task to handle shutdown
        asyncio.create_task(self.shutdown())

    async def shutdown(self, reason: str = "user_request", timeout: int = 30):
        """Perform graceful shutdown with state preservation."""

        # 1. Prevent new work
        self.state_machine.set_status(PipelineStatus.STOPPING)

        # 2. Wait for agents to reach safe point (with timeout)
        try:
            await asyncio.wait_for(
                self._wait_for_agents_safe_point(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print(f"⚠️  Timeout waiting for agents, forcing save")

        # 3. Capture agent snapshots
        snapshots = await self._capture_agent_snapshots()

        # 4. Mark interrupted work items
        interrupted = await self._mark_interrupted_items()

        # 5. Save state atomically
        await self._save_state_atomic(
            reason=reason,
            snapshots=snapshots,
            interrupted_items=interrupted
        )

        # 6. Clean exit
        print("✅ State saved successfully. Safe to exit.")
        self.state_machine.set_status(PipelineStatus.STOPPED)

    async def _save_state_atomic(self, **kwargs):
        """Save state atomically (write temp, then rename)."""
        state = self.state_machine._state
        state.shutdown_reason = kwargs.get('reason')
        state.agent_snapshots = kwargs.get('snapshots', [])
        state.interrupted_work_items = kwargs.get('interrupted_items', [])
        state.last_checkpoint = datetime.now()

        # Write to temp file
        temp_path = self.state_machine.state_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2, default=str)

        # Verify JSON is valid
        with open(temp_path, 'r') as f:
            json.load(f)  # Will raise if invalid

        # Atomic rename
        temp_path.rename(self.state_machine.state_path)

    def check_should_stop(self) -> bool:
        """Check if shutdown was requested. Call this in loops."""
        return self.shutdown_requested
```

### Resume After Shutdown
```python
# orchestrator/resume.py

class ResumeManager:
    """Handles resuming from saved state."""

    async def resume(self, state: PipelineState) -> ResumePoint:
        """Determine where to resume from."""

        # 1. Check for crash (heartbeat too old)
        if self._detect_crash(state):
            print("⚠️  Detected previous crash. Recovering...")
            return await self._recover_from_crash(state)

        # 2. Check for interrupted work items
        if state.interrupted_work_items:
            print(f"📋 Found {len(state.interrupted_work_items)} interrupted items")
            # Re-queue them as TODO (they weren't completed)
            for item_id in state.interrupted_work_items:
                await self.work_tracker.update_work_item(
                    item_id,
                    {"status": WorkItemStatus.TODO}
                )

        # 3. Determine resume phase
        resume_phase = self._find_resume_phase(state)

        # 4. Inject context from agent snapshots
        context = self._build_resume_context(state.agent_snapshots)

        return ResumePoint(
            phase=resume_phase,
            context=context,
            work_items_to_retry=state.interrupted_work_items
        )

    def _detect_crash(self, state: PipelineState) -> bool:
        """Detect if previous run crashed (heartbeat stale)."""
        if not state.heartbeat:
            return False
        stale_threshold = timedelta(minutes=5)
        return datetime.now() - state.heartbeat > stale_threshold
```

### CLI Stop Command
```bash
# Interactive stop (from another terminal)
python main.py --stop

# Or send signal directly
kill -SIGTERM <pid>

# Or press CTRL+C in the running terminal
^C
```

### CLI Output During Shutdown
```
^C
⚠️  Shutdown requested (signal 2)
Saving state and stopping gracefully...

[1/5] Signaling agents to finish current step...
[2/5] Waiting for agent to reach safe point... (timeout: 30s)
[3/5] Capturing agent snapshot...
      - Phase: implement
      - Work item: TASK-42 (In Progress)
      - Last tool: Edit (src/api/auth.py)
[4/5] Marking interrupted items...
      - TASK-42 → TODO (will retry on resume)
[5/5] Saving state atomically...

✅ State saved successfully!

To resume: python main.py --resume
To check status: python main.py --status
```

---

## Configuration Example (orchestrator.yaml)

```yaml
project:
  name: "My App"
  directory: "./my_project"

backend:
  type: "json"  # or "linear"

autonomy:
  mode: "checkpoint"  # or "full"

phases:
  ideation:
    enabled: true
    pattern: "swarm"
    checkpoint_pause: true
  architecture:
    enabled: true
    pattern: "swarm"
    checkpoint_pause: true
  implement:
    enabled: true
    pattern: "single"
    checkpoint_pause: false
  deploy:
    enabled: false

agent:
  model: "claude-opus-4-5-20251101"
  max_sessions: 1000

error_recovery:
  max_consecutive_errors: 3
  stall_timeout_minutes: 30
```

---

## Deployment Modes

### Mode 1: Local CLI (Interactive Multi-Project)
```
$ python main.py

🤖 Orchestrator Ready
Type a command or describe what you want to build.

> /projects
📋 Your Projects:
  ID    Name            Status      Phase           Progress
  ───────────────────────────────────────────────────────────
  1     task-manager    running     implement       32/50 (64%)
  2     ai-chatbot      completed   -               50/50 (100%)
  3     e-commerce      paused      architecture    awaiting approval

> /status 1
📊 Project: task-manager
   Status: Running
   Phase: Implement
   Progress: 32/50 work items (64%)
   Last activity: 2 hours ago
   Backend: Linear (PROJ-456)

> /resume 3
Resuming e-commerce...
📋 Architecture phase awaiting approval.
   Do you approve the architecture? [Y/n/view]
> view
[Shows architecture summary...]
> y
✅ Approved. Starting Task Breakdown phase...

> Build me a portfolio website with blog
🆕 Starting new project...
   Project name? [portfolio-blog]:
> my-portfolio
   Creating project 'my-portfolio'...
   Starting Ideation phase with swarm (3 agents)...

> /stop
⚠️ Stopping my-portfolio...
   Saving state... Done.
   Project paused at: Ideation phase (3 agents running)

> /help
Available commands:
  /projects         List all projects
  /status [id]      Show project status (current if no id)
  /resume <id>      Resume a paused project
  /stop             Stop current project gracefully
  /help             Show this help

Or just type what you want to build to start a new project.
```

### Mode 2: Docker (REST API Only)
```bash
# Start with bundled PostgreSQL
docker-compose up -d

# Or connect to external database
docker run -d \
  -p 8080:8080 \
  -e DATABASE_URL=postgresql://user:pass@external-host:5432/orchestrator \
  -e CLAUDE_CODE_OAUTH_TOKEN=$TOKEN \
  orchestrator:latest
```

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects` | GET | List all projects |
| `/projects` | POST | Create new project with idea |
| `/projects/{id}` | GET | Get project status |
| `/projects/{id}/resume` | POST | Resume paused project |
| `/projects/{id}/stop` | POST | Stop project gracefully |
| `/projects/{id}/approve` | POST | Approve checkpoint |

---

## Database Schema (PostgreSQL)

```sql
-- Projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    -- 'not_started', 'running', 'paused', 'completed', 'failed', 'stopped'
    current_phase VARCHAR(50),
    config JSONB,  -- OrchestratorConfig as JSON
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Pipeline state (one per project)
CREATE TABLE pipeline_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    phases JSONB NOT NULL,  -- Dict of PhaseState
    last_checkpoint TIMESTAMP,
    heartbeat TIMESTAMP,
    shutdown_requested BOOLEAN DEFAULT FALSE,
    shutdown_reason VARCHAR(100),
    agent_snapshots JSONB,  -- List of AgentSnapshot
    interrupted_work_items JSONB,  -- List of work item IDs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Work items (features/tasks)
CREATE TABLE work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'todo',
    -- 'todo', 'in_progress', 'done', 'blocked'
    priority INTEGER DEFAULT 3,  -- 1=urgent, 4=low
    phase VARCHAR(50),
    parent_id UUID REFERENCES work_items(id),
    dependencies JSONB,  -- List of work item IDs
    labels JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Work item comments (for handoff notes)
CREATE TABLE work_item_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID REFERENCES work_items(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Phase outputs (stored artifacts)
CREATE TABLE phase_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,
    output_type VARCHAR(100),  -- 'requirements', 'architecture', 'features', etc.
    content JSONB,
    file_path VARCHAR(500),  -- If stored as file
    created_at TIMESTAMP DEFAULT NOW()
);

-- Session logs (for debugging/audit)
CREATE TABLE session_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50),
    session_number INTEGER,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    status VARCHAR(50),
    summary TEXT,
    error TEXT,
    tool_calls JSONB  -- List of tool calls made
);

-- Indexes for common queries
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_work_items_project ON work_items(project_id);
CREATE INDEX idx_work_items_status ON work_items(status);
CREATE INDEX idx_pipeline_states_project ON pipeline_states(project_id);
```

### Data Model Classes
```python
# database/models.py
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

class Project(Base):
    __tablename__ = 'projects'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String)
    status = Column(String(50), default='not_started')
    current_phase = Column(String(50))
    config = Column(JSON)
    created_at = Column(DateTime, server_default='now()')
    updated_at = Column(DateTime, server_default='now()', onupdate='now()')

    # Relationships
    pipeline_state = relationship("PipelineState", back_populates="project", uselist=False)
    work_items = relationship("WorkItem", back_populates="project")
    phase_outputs = relationship("PhaseOutput", back_populates="project")
    session_logs = relationship("SessionLog", back_populates="project")
```

---

## Input Adapter System

The orchestrator receives ideas/input through pluggable adapters:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   CLI Adapter    │     │   API Adapter    │     │  Future Adapter  │
│  (Interactive)   │     │  (REST/WebSocket)│     │   (Slack, etc.)  │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      InputAdapter         │
                    │   Abstract Interface      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       Orchestrator        │
                    └───────────────────────────┘
```

### CLI Chat Flow (Default)
```bash
$ python main.py

🤖 Autonomous Orchestrator v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What would you like to build?
> Build a task management app with AI prioritization

Got it! Let me understand your requirements better...

[Ideation Phase - 3 agents brainstorming...]
Agent 1: Analyzing user requirements...
Agent 2: Evaluating technical feasibility...
Agent 3: Identifying edge cases...

📋 Requirements Summary:
1. Task CRUD operations
2. AI-powered priority suggestions
3. Due date reminders
...

Does this look right? [Y/n/edit]
> y

[Architecture Phase starting...]
```

### InputAdapter Interface
```python
# adapters/base.py
class InputAdapter(ABC):
    @abstractmethod
    async def get_initial_idea(self) -> str:
        """Get the initial project idea from user."""
        pass

    @abstractmethod
    async def get_approval(self, summary: str, phase: str) -> bool:
        """Get user approval at checkpoints."""
        pass

    @abstractmethod
    async def get_clarification(self, question: str) -> str:
        """Ask user for clarification during phases."""
        pass

    @abstractmethod
    async def show_progress(self, status: PipelineState) -> None:
        """Display current progress to user."""
        pass

    @abstractmethod
    async def show_error(self, error: str, options: List[str]) -> str:
        """Show error and get user decision."""
        pass
```

---

## CLI Commands

```bash
# Start new project (interactive CLI chat)
python main.py

# Start with config file
python main.py --config orchestrator.yaml

# Resume paused pipeline
python main.py --resume

# Check status
python main.py --status

# Non-interactive mode (read idea from file)
python main.py --idea-file idea.md --no-interactive

# API mode (future)
python main.py --api --port 8080

# Docker
docker-compose up -d
docker-compose logs -f
```

---

## Critical Files Reference

| File | Path | Purpose |
|------|------|---------|
| Entry point | `autonomous_agent_demo.py` | Current entry (keep for backwards compat) |
| Session loop | `agent.py` | `run_agent_session()` to wrap in phases |
| Client creation | `client.py` | `create_client()` to extend |
| Security | `security.py` | Do not modify |
| Progress | `progress.py` | Extend for multi-backend |
| Init prompt | `prompts/initializer_prompt.md` | Template for Phase 4 |
| Coding prompt | `prompts/coding_prompt.md` | Template for Phase 5 |

---

## Implementation Order

### Foundation Layer
1. **Sprint 1**: `config/`, `database/` (PostgreSQL models, migrations, connection) ✅ **COMPLETED**
2. **Sprint 2**: `orchestrator/state_machine.py`, `orchestrator/shutdown.py`, `orchestrator/resume.py`, `orchestrator/heartbeat.py` ✅ **COMPLETED**

### Interaction Layer
3. **Sprint 3**: `adapters/base.py`, `adapters/cli_adapter.py` (interactive CLI with slash commands) ✅ **COMPLETED**
4. **Sprint 4**: `api/` (FastAPI REST endpoints for Docker mode) ✅ **COMPLETED**

### Core Orchestration
5. **Sprint 5**: `phases/base.py`, `phases/initialize.py`, `phases/implement.py`, `orchestrator/phase_runner.py` ✅ **COMPLETED**
6. **Sprint 6**: New phases (ideation, architecture, task_breakdown, testing, deploy) ✅ **COMPLETED**
7. **Sprint 7**: `orchestrator/swarm_controller.py`, `orchestrator/aggregator.py` ✅ **COMPLETED**
8. **Sprint 8**: `orchestrator/error_recovery.py` ✅ **COMPLETED**

### Backends & Deployment
9. **Sprint 9**: `backends/` (abstract interface, JSON backend, Linear backend) ✅ **COMPLETED**
10. **Sprint 10**: `Dockerfile`, `docker-compose.yml` with PostgreSQL ✅ **COMPLETED**

---

## Success Criteria

### Local CLI Mode
- [ ] `python main.py` starts interactive CLI
- [ ] `/projects` lists all projects from PostgreSQL
- [ ] `/status <id>` shows project details
- [ ] `/resume <id>` resumes paused project
- [ ] `/stop` gracefully stops current project
- [ ] `/help` shows available commands
- [ ] Typing a sentence starts a new project
- [ ] Checkpoints pause and ask for approval in CLI

### Docker API Mode
- [ ] `docker-compose up` starts orchestrator + PostgreSQL
- [ ] `POST /projects` creates new project with idea
- [ ] `GET /projects` lists all projects
- [ ] `GET /projects/{id}` shows project status
- [ ] `POST /projects/{id}/resume` resumes project
- [ ] `POST /projects/{id}/stop` stops project
- [ ] External database works (`DATABASE_URL` env var)

### Multi-Project Management
- [ ] Multiple projects tracked in PostgreSQL
- [ ] Each project has independent state
- [ ] Project history preserved after completion
- [ ] Can resume any paused project

### Core Orchestration
- [ ] Phases execute in order with persistence
- [ ] Swarm pattern works for ideation/architecture
- [ ] Both JSON and Linear work item backends work

### Robustness & Resilience
- [ ] CTRL+C triggers graceful shutdown (not crash)
- [ ] State saved atomically (no corruption)
- [ ] Agent snapshots captured before shutdown
- [ ] Interrupted work items re-queued on resume
- [ ] Heartbeat detects crashes (recovery mode)
- [ ] Resume works after shutdown or crash
- [ ] Never loses more than 60 seconds of work

### Deployment
- [ ] Docker container runs with bundled PostgreSQL
- [ ] Docker container runs with external PostgreSQL
- [ ] SIGTERM handled properly in Docker

---

## Key Interface Definitions

### WorkTracker (backends/base.py)
```python
class WorkTracker(ABC):
    @abstractmethod
    async def initialize(self, project_dir: Path) -> Project: ...

    @abstractmethod
    async def create_work_item(self, item: WorkItem) -> WorkItem: ...

    @abstractmethod
    async def update_work_item(self, item_id: str, updates: Dict) -> WorkItem: ...

    @abstractmethod
    async def get_next_work_item(self, project_id: str, phase: str) -> Optional[WorkItem]: ...

    @abstractmethod
    async def get_progress_summary(self, project_id: str) -> Dict[str, int]: ...
```

### Phase (phases/base.py)
```python
class Phase(ABC):
    name: str
    display_name: str

    @abstractmethod
    async def run(
        self,
        input_data: Any,
        config: PhaseConfig,
        work_tracker: WorkTracker,
        project_dir: Path
    ) -> PhaseResult: ...

    @abstractmethod
    def get_prompts(self, pattern: PlanningPattern) -> List[str]: ...
```

---

*Created: 2025-12-23*
*Updated: 2025-12-24*
*Status: ALL SPRINTS COMPLETED (40+ source files, Docker ready)*
