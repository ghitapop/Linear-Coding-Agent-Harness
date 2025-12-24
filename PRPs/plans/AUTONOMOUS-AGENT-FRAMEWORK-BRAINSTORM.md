# Autonomous Coding Agent Framework - Brainstorm Notes

## Context
Brainstorming session for building a coding agent framework based on Claude Code's native capabilities (Task tool with subagents) that can autonomously develop software based on requirement plans.

---

## Key Insights from Research

### Claude Code Native Multi-Agent
- Claude Code's Task tool already supports parallel subagents
- 90.2% better performance than single-agent approaches
- No external framework needed (no CrewAI, AutoGen, etc.)
- All within one session, one subscription

### Anthropic's "Effective Harnesses for Long-Running Agents"
Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

#### Core Principles
1. **Two-Agent Architecture**
   - Initializer Agent: Sets up environment (first run only)
   - Coding Agent: Handles incremental progress (subsequent sessions)

2. **Session Handoff Problem**
   - Agents work in discrete sessions without memory
   - Solution: Treat like multi-shift engineering team with handoff documentation

3. **Environmental Scaffolding**
   | Component | Purpose |
   |-----------|---------|
   | `init.sh` | Automates dev server startup & testing |
   | `claude-progress.txt` | Logs agent actions & project state |
   | Git history | Changeset documentation & recovery |
   | Feature list (JSON) | Structured requirements with `passes: true/false` |

4. **Feature Granularity**
   - Decompose high-level requests into 200+ discrete, testable features
   - Use JSON (not Markdown) - models less likely to modify structured data

5. **Incremental Progress Pattern**
   - One feature per session
   - Commit with descriptive messages
   - Update progress documentation

6. **Quality Gates**
   - Test as end-user, not just code syntax
   - Browser automation (Puppeteer MCP) for real testing
   - Validate previous session's work before starting new work

---

## Framework Architecture

### High-Level Flow
```
User Idea → Orchestrator → Swarm (Brainstorm) → Requirements
         → Swarm (Architecture) → Tech Stack
         → Task Breakdown → features.json (200+ items)
         → Initialize → Scaffolding
         → Implement (one feature at a time) → Code
         → Review & Test → Quality Gate
         → Loop until all features complete
```

### Visual Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                            │
│  • Manages pipeline state                                       │
│  • Spawns agent swarms (max 3)                                  │
│  • Aggregates & grades results                                  │
│  • Maintains progress.json + git history                        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
     ┌────────────────────────────┼────────────────────────────┐
     ▼                            ▼                            ▼
┌─────────────┐            ┌─────────────┐            ┌─────────────┐
│ PHASE 1     │            │ PHASE 2     │            │ PHASE 3     │
│ Brainstorm  │     →      │ Architecture│     →      │ Task        │
│ Swarm (3)   │            │ Swarm (3)   │            │ Breakdown   │
└─────────────┘            └─────────────┘            └─────────────┘
     │                            │                            │
     ▼                            ▼                            ▼
┌─────────────┐            ┌─────────────┐            ┌─────────────┐
│ PHASE 4     │            │ PHASE 5     │            │ PHASE 6     │
│ Implement   │     →      │ Review &    │     →      │ Integration │
│ (1 feature) │            │ Test        │            │ & Validate  │
└─────────────┘            └─────────────┘            └─────────────┘
```

---

## Development Pipeline

| Phase | Agents | Input | Output | Quality Gate |
|-------|--------|-------|--------|--------------|
| **1. Ideation** | 3 parallel | Raw idea | Product requirements | Consensus vote |
| **2. Architecture** | 3 parallel | Requirements | Tech stack, components | Review & approve |
| **3. Task Breakdown** | 1 | Architecture | `features.json` (200+ items) | Structured JSON |
| **4. Initialize** | 1 (Initializer) | features.json | `init.sh`, scaffolding | Dev server runs |
| **5. Implement** | 1 per feature | One feature | Code + commit | Tests pass |
| **6. Review** | 1 (QA agent) | Code | Issues/fixes | E2E tests pass |
| **7. Loop** | - | Next feature | Repeat 5-6 | All features done |

---

## Core Components to Build

1. **Orchestrator** - Pipeline manager with state persistence
2. **Swarm Spawner** - Uses Claude Code Task tool for parallel agents
3. **Aggregator** - Grades/votes on swarm outputs (can borrow from voting systems)
4. **Progress Tracker** - `features.json` + `progress.json` management
5. **Quality Gate Runner** - Validates work before proceeding
6. **Session Manager** - Handles handoffs between agent sessions

---

## Session State Management

Each session starts with:
1. `pwd` - Confirm working directory
2. Review `git log` + `progress.json`
3. Read `features.json`, pick next incomplete item
4. Run dev server, validate previous work
5. Fix regressions before new work
6. Implement ONE feature
7. Commit + update progress
8. End session cleanly

---

## Swarm Patterns

### Brainstorming Swarm (3 agents)
```
Agent 1 → Focus on "User requirements & use cases"
Agent 2 → Focus on "Technical feasibility & constraints"
Agent 3 → Focus on "Edge cases & potential issues"
     ↓
Orchestrator aggregates → Produces comprehensive requirements
```

### Architecture Swarm (3 agents)
```
Agent 1 → Focus on "System design & components"
Agent 2 → Focus on "Data models & API design"
Agent 3 → Focus on "Infrastructure & deployment"
     ↓
Orchestrator aggregates → Produces architecture document
```

---

## Key Files Structure

```
project/
├── .claude/
│   ├── features.json      # 200+ features with passes: true/false
│   ├── progress.json      # Current state, completed features
│   ├── architecture.json  # System design decisions
│   └── session-log.md     # Handoff notes between sessions
├── init.sh                # Environment setup script
├── src/                   # Application code
└── tests/                 # Test files
```

### features.json Example
```json
{
  "project": "My App",
  "total_features": 215,
  "completed": 12,
  "features": [
    {
      "id": 1,
      "name": "User authentication - login form",
      "description": "Create login form with email/password",
      "priority": "high",
      "dependencies": [],
      "passes": true,
      "completed_at": "2025-12-23T10:00:00Z"
    },
    {
      "id": 2,
      "name": "User authentication - session management",
      "description": "Implement JWT session tokens",
      "priority": "high",
      "dependencies": [1],
      "passes": false,
      "completed_at": null
    }
  ]
}
```

---

## Why Native Claude Code > External Frameworks

| Aspect | External (CrewAI, AutoGen) | Native (Task tool) |
|--------|----------------------------|---------------------|
| Setup | Install packages, configure | Zero - built in |
| Cost | API costs per agent | One subscription |
| Complexity | High | Low |
| Context sharing | Manual | Automatic |
| Parallel execution | Framework dependent | Native support |

---

## References

- Anthropic: "Effective Harnesses for Long-Running Agents" - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Claude Code Task tool (native subagent capability)
- External frameworks (for comparison): CrewAI, AutoGen, OpenAI Swarm, LangGraph

---

*Created: 2025-12-23*
*Status: Brainstorming phase - ready to apply to real project*
