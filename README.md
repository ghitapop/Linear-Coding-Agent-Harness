# Autonomous Coding Agent Framework

A framework for running autonomous coding agents with the Claude Agent SDK. This repository provides two systems:

1. **Demo Mode** (`autonomous_agent_demo.py`): Simple two-agent pattern with Linear integration for issue tracking
2. **Orchestrator Framework** (`main.py`): Full multi-phase pipeline with state persistence, swarm parallelism, and multiple backend options

## Key Features

- **Multi-Phase Pipeline**: Ideation, architecture, task breakdown, implementation, testing, and deployment
- **State Persistence**: Resumable pipelines with crash recovery
- **Swarm Parallelism**: Run multiple agents in parallel for brainstorming phases
- **Multiple Backends**: PostgreSQL, JSON file, or Linear for work item tracking
- **Docker Support**: Ready-to-deploy containerized setup
- **Linear Integration**: Real-time visibility in your Linear workspace (Demo Mode)
- **Browser Testing**: Puppeteer MCP for UI verification
- **Defense-in-Depth Security**: Sandboxed execution with command allowlisting

## Prerequisites

### 1. Install Claude Code CLI and Python SDK

```bash
# Install Claude Code CLI (latest version required)
npm install -g @anthropic-ai/claude-code

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Set Up Authentication

You need authentication tokens based on your usage:

**Claude Code OAuth Token (Required):**
```bash
# Generate the token using Claude Code CLI
claude setup-token

# Set the environment variable
export CLAUDE_CODE_OAUTH_TOKEN='your-oauth-token-here'
```

**Linear API Key (Optional - for Demo Mode or Linear backend):**
```bash
# Get your API key from: https://linear.app/YOUR-TEAM/settings/api
export LINEAR_API_KEY='lin_api_xxxxxxxxxxxxx'
```

**Database URL (Optional - for Orchestrator with PostgreSQL backend):**
```bash
export DATABASE_URL='postgresql://user:pass@localhost:5432/coding_agent_harness_db'
```

### 3. Verify Installation

```bash
claude --version  # Should be latest version
pip show claude-code-sdk  # Check SDK is installed
```

## Quick Start

### Demo Mode (Linear-Integrated)

Simple two-agent pattern for building applications with Linear issue tracking:

```bash
python autonomous_agent_demo.py --project-dir ./my_project
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3
python autonomous_agent_demo.py --project-dir ./my_project --model claude-sonnet-4-5-20250929
```

### Orchestrator Framework

Full multi-phase pipeline with state management:

```bash
python main.py                                    # Interactive CLI (default)
python main.py --config orchestrator.yaml         # Custom config file
python main.py --resume                           # Resume paused project
python main.py --status                           # Check project status
python main.py --stop                             # Graceful shutdown
python main.py --api --port 8080                  # API server mode
python main.py --idea-file idea.md --no-interactive  # Non-interactive mode
```

### Docker

```bash
# With bundled PostgreSQL (recommended for development, uses port 5433)
docker-compose --profile with-db up -d --build

# With external database (Supabase, Neon, Railway, etc.)
docker-compose --profile external-db up -d --build

# Development database only
docker-compose --profile dev-db up postgres-dev

# Stop containers
docker-compose --profile with-db down

# Stop and delete PostgreSQL volume (required for major version upgrades)
docker-compose --profile with-db down -v
```

**Container Names:**
| Container | Profile | Purpose |
|-----------|---------|---------|
| `harness_app` | with-db, external-db | Application container |
| `harness_db` | with-db | Bundled PostgreSQL (port 5433) |
| `harness_db_dev` | dev-db | Development PostgreSQL (port 5432) |

**Note:** Bundled PostgreSQL uses port 5433 (not default 5432) and stores data in the `coding-agent-harness-data` volume.

### Database Migrations

```bash
alembic upgrade head                              # Apply all migrations
alembic revision --autogenerate -m "description"  # Create new migration
```

### Tests

```bash
python test_security.py
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Purpose | Default |
|----------|---------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code auth (`claude setup-token`) | Required |
| `LINEAR_API_KEY` | Linear API access | Optional (Demo mode, Linear backend) |
| `DATABASE_URL` | PostgreSQL connection string | Optional (Orchestrator with postgres backend) |
| `WORKSPACE_PATH` | Workspace directory for projects | `./workspaces` |
| `API_PORT` | Port for API server | `8080` |
| `POSTGRES_DB` | Database name (bundled PostgreSQL) | `coding_agent_harness_db` |
| `POSTGRES_USER` | Database user (bundled PostgreSQL) | `postgres` |
| `POSTGRES_PASSWORD` | Database password (bundled PostgreSQL) | `postgres` |
| `POSTGRES_PORT` | PostgreSQL port (bundled PostgreSQL) | `5433` |
| `AGENT_MODEL` | Claude model to use | `claude-opus-4-5-20251101` |
| `MAX_SESSIONS` | Maximum agent sessions | `1000` |

## Architecture

### Demo Mode: Two-Agent Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    LINEAR-INTEGRATED WORKFLOW               │
├─────────────────────────────────────────────────────────────┤
│  app_spec.txt ──► Initializer Agent ──► Linear Issues (50) │
│                                              │               │
│                    ┌─────────────────────────▼──────────┐   │
│                    │        LINEAR WORKSPACE            │   │
│                    │  ┌────────────────────────────┐    │   │
│                    │  │ Issue: Auth - Login flow   │    │   │
│                    │  │ Status: Todo → In Progress │    │   │
│                    │  │ Comments: [session notes]  │    │   │
│                    │  └────────────────────────────┘    │   │
│                    └────────────────────────────────────┘   │
│                                              │               │
│                    Coding Agent queries Linear              │
│                    ├── Search for Todo issues               │
│                    ├── Update status to In Progress         │
│                    ├── Implement & test with Puppeteer      │
│                    ├── Add comment with implementation notes│
│                    └── Update status to Done                │
└─────────────────────────────────────────────────────────────┘
```

1. **Initializer Agent (Session 1):** Reads `app_spec.txt`, creates Linear project with 50 issues, sets up project structure, writes `.linear_project.json`
2. **Coding Agent (Sessions 2+):** Queries Linear for highest-priority Todo, claims it, implements with Puppeteer verification, marks Done, updates META issue

### Orchestrator Framework: Multi-Phase Pipeline

Phases execute sequentially with optional checkpoints:

```
ideation → architecture → task_breakdown → initialize → implement → testing → deploy
```

**Planning phases are enabled by default** when running `python main.py`. The user's idea flows through:
1. **Ideation** → produces `PRPs/plans/requirements.md`
2. **Architecture** → produces `PRPs/plans/architecture.md`
3. **Task Breakdown** → produces `PRPs/plans/tasks.md`
4. **Initialize/Implement** → executes the tasks

**Execution Patterns:**
- `SINGLE`: One agent per phase
- `SWARM`: Multiple parallel agents with result aggregation (used by ideation, architecture)

**Ideation Swarm:** Runs 3 specialized agents in parallel:
- User requirements specialist (personas, user stories, journeys)
- Technical feasibility specialist (stack, integrations, security)
- Edge cases specialist (errors, failure modes, accessibility)

Results are aggregated into a unified requirements document.

**State Management:**
- Pipeline state persisted to `.orchestrator_state.json`
- Resumable after interruption via `--resume`
- Checkpoint approvals pause for user confirmation

## Project Structure

```
linear-agent-harness/
├── autonomous_agent_demo.py  # Demo mode entry point
├── main.py                   # Orchestrator framework entry point
├── agent.py                  # Agent session logic
├── client.py                 # Claude SDK + MCP client configuration
├── security.py               # Bash command allowlist and validation
├── progress.py               # Progress tracking utilities
├── prompts.py                # Prompt loading utilities
├── linear_config.py          # Linear configuration constants
├── orchestrator.yaml         # Default orchestrator configuration
├── docker-compose.yml        # Docker deployment configuration
├── Dockerfile                # Container image definition
├── alembic.ini               # Database migration configuration
│
├── orchestrator/             # Pipeline orchestration
│   ├── phase_runner.py       # Executes phases sequentially with retry
│   ├── state_machine.py      # Persists pipeline state for resumability
│   ├── swarm_controller.py   # Runs parallel agents with aggregation
│   ├── aggregator.py         # Result aggregation logic
│   ├── error_recovery.py     # Error handling and recovery
│   ├── heartbeat.py          # Liveness monitoring
│   ├── resume.py             # Resume logic for interrupted runs
│   └── shutdown.py           # Graceful shutdown handling
│
├── phases/                   # Phase implementations
│   ├── base.py               # Phase base class
│   ├── ideation.py           # Brainstorming phase
│   ├── architecture.py       # System design phase
│   ├── task_breakdown.py     # Work item creation
│   ├── initialize.py         # Project setup
│   ├── implement.py          # Feature implementation
│   ├── testing.py            # Test execution
│   └── deploy.py             # Deployment phase
│
├── backends/                 # Work item tracking backends
│   ├── base.py               # WorkTracker interface
│   ├── postgres_backend.py   # PostgreSQL backend
│   ├── json_backend.py       # Local file backend
│   └── linear_backend.py     # Linear.app backend
│
├── adapters/                 # UI adapters
│   ├── base.py               # Adapter interface
│   ├── cli_adapter.py        # Interactive terminal UI
│   └── api_adapter.py        # REST API callbacks
│
├── api/                      # FastAPI server
│   ├── main.py               # App factory
│   ├── schemas.py            # Pydantic models
│   └── routes/
│       ├── health.py         # Health check endpoint
│       └── projects.py       # Project management endpoints
│
├── config/                   # Configuration
│   ├── loader.py             # YAML config with env var substitution
│   └── schema.py             # Config schema definitions
│
├── database/                 # Database layer
│   ├── models.py             # SQLAlchemy ORM models
│   ├── connection.py         # Connection management
│   ├── repository.py         # Data access patterns
│   └── migrations/           # Alembic migrations
│
├── prompts/                  # Agent prompts
│   ├── app_spec.txt          # Application specification
│   ├── initializer_prompt.md # First session prompt
│   ├── coding_prompt.md      # Continuation session prompt
│   ├── ideation/             # Ideation phase prompts
│   │   ├── brainstorm.md     # Single-agent prompt (fallback)
│   │   ├── brainstorm_user.md        # Swarm: user requirements
│   │   ├── brainstorm_technical.md   # Swarm: technical feasibility
│   │   ├── brainstorm_edge_cases.md  # Swarm: edge cases & risks
│   │   └── aggregate.md      # Combines swarm outputs
│   ├── architecture/         # Architecture phase prompts
│   └── task_breakdown/       # Task breakdown phase prompts
│
└── PRPs/plans/               # Generated planning documents (per project)
    ├── requirements.md       # Output from ideation phase
    ├── architecture.md       # Output from architecture phase
    └── tasks.md              # Output from task breakdown phase
```

## Configuration

The orchestrator is configured via `orchestrator.yaml`:

```yaml
project:
  name: "My Project"
  directory: "./my_project"

backend:
  type: "postgres"  # Options: postgres | json | linear

autonomy: "checkpoint"  # Options: full | checkpoint

phases:
  ideation:
    enabled: true
    pattern: "swarm"        # swarm | single
    checkpoint_pause: true  # Pause for approval
    max_retries: 3
    timeout_minutes: 60

  architecture:
    enabled: true
    pattern: "swarm"
    checkpoint_pause: true

  task_breakdown:
    enabled: true
    pattern: "single"
    checkpoint_pause: true

  initialize:
    enabled: true
    pattern: "single"
    checkpoint_pause: false

  implement:
    enabled: true
    pattern: "single"
    checkpoint_pause: false
    max_retries: 5
    timeout_minutes: 240

  testing:
    enabled: false  # Optional
    pattern: "single"

  deploy:
    enabled: false  # Optional
    pattern: "single"

agent:
  model: "claude-opus-4-5-20251101"
  max_sessions: 1000
  session_timeout_minutes: 120

error_recovery:
  max_consecutive_errors: 3
  stall_timeout_minutes: 30
  retry_delay_seconds: 5
```

## Security Model

This framework uses defense-in-depth security (see `security.py` and `client.py`):

1. **OS-level Sandbox:** Bash commands run in an isolated environment
2. **Filesystem Restrictions:** File operations restricted to project directory
3. **Bash Allowlist:** Only specific commands permitted (npm, node, git, etc.)
4. **Extra Validation:** Commands like `pkill`, `chmod`, `init.sh` have custom validators
5. **MCP Permissions:** Tools explicitly allowed in security settings

## MCP Servers

| Server | Transport | Purpose |
|--------|-----------|---------|
| **Linear** | HTTP (`mcp.linear.app`) | Issue CRUD, project management |
| **Puppeteer** | stdio | Browser automation for UI testing |

## Extending the System

**Add bash commands:** Add to `ALLOWED_COMMANDS` in `security.py`. Commands in `COMMANDS_NEEDING_EXTRA_VALIDATION` require custom validators.

**Add new phase:** Extend `Phase` base class in `phases/base.py`, implement `run()`, register in phase runner.

**Add backend:** Implement `WorkTracker` interface in `backends/base.py`.

**Custom prompts:** Edit templates in `prompts/` directory.

## Customization

### Changing the Application (Demo Mode)

Edit `prompts/app_spec.txt` to specify a different application to build.

### Adjusting Issue Count (Demo Mode)

Edit `prompts/initializer_prompt.md` and change "50 issues" to your desired count.

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

## Keyboard Controls

| Key | Action |
|-----|--------|
| **ESC** | Interrupt current operation, return to prompt |
| **CTRL+C** | Same as ESC (interrupt, not exit) |
| **Enter** | Continue current project (after interrupt) |
| **/new** | Start a new project (abandons current) |
| **/quit** or **/exit** | Exit the application |
| **/stop** | Stop current project gracefully |
| **/help** | Show available commands |

## Troubleshooting

**"CLAUDE_CODE_OAUTH_TOKEN not set"**
Run `claude setup-token` to generate a token, then export it.

**"LINEAR_API_KEY not set"**
Get your API key from `https://linear.app/YOUR-TEAM/settings/api`

**"DATABASE_URL not set" (Orchestrator)**
Set your PostgreSQL connection string or use the `json` backend instead.

**"Appears to hang on first run"**
Normal behavior. The initializer is creating a Linear project and 50 issues with detailed descriptions. Watch for `[Tool: mcp__linear__create_issue]` output.

**"Command blocked by security hook"**
The agent tried to run a disallowed command. Add it to `ALLOWED_COMMANDS` in `security.py` if needed.

**"MCP server connection failed"**
Verify your `LINEAR_API_KEY` is valid and has appropriate permissions. The Linear MCP server uses HTTP transport at `https://mcp.linear.app/mcp`.

## Generated Project Files

After running, your project directory will contain:

**Demo Mode:**
```
my_project/
├── .linear_project.json      # Linear project state (marker file)
├── app_spec.txt              # Copied specification
├── init.sh                   # Environment setup script
├── .claude_settings.json     # Security settings
└── [application files]       # Generated application code
```

**Orchestrator Framework:**
```
my_project/
├── .orchestrator_state.json  # Pipeline state for resumability
├── PRPs/
│   └── plans/
│       ├── requirements.md   # From ideation phase
│       ├── architecture.md   # From architecture phase
│       └── tasks.md          # From task breakdown phase
└── [application files]       # Generated application code
```

## License

MIT License - see [LICENSE](LICENSE) for details.
