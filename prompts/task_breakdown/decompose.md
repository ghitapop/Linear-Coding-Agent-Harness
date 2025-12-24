# Task Breakdown Phase - Feature Decomposition

## Your Task
Break down the architecture into {{MIN_TASKS}}-{{MAX_TASKS}} granular, implementable tasks.

## Architecture
{{ARCHITECTURE}}

## Requirements Reference
{{REQUIREMENTS}}

## Instructions

### 1. Identify Implementation Phases

Group work into logical phases:
1. **Foundation** - Project setup, configuration, base infrastructure
2. **Data Layer** - Database schema, models, migrations
3. **Backend Core** - API endpoints, business logic, services
4. **Frontend Core** - Pages, components, state management
5. **Integration** - Connect frontend to backend
6. **Features** - Implement each feature from requirements
7. **Testing** - Unit, integration, e2e tests
8. **Polish** - Error handling, edge cases, performance

### 2. Create Granular Tasks

Each task MUST be:
- **Atomic:** Completable independently (1-4 hours of work)
- **Specific:** Clear what needs to be done
- **Testable:** Has verifiable acceptance criteria
- **Sized Right:** Not too big, not too small

### 3. Assign Priorities

Use this priority scheme:
- **P1 (Urgent):** Blocks other work, core infrastructure
- **P2 (High):** Primary features, critical path items
- **P3 (Medium):** Secondary features, enhancements
- **P4 (Low):** Nice-to-haves, polish, optimization

### 4. Define Dependencies

For each task, identify:
- What must be completed before this task
- What this task unblocks
- Ensure no circular dependencies

### 5. Estimate Complexity

Rate each task:
- **XS:** < 30 minutes
- **S:** 30 min - 1 hour
- **M:** 1-2 hours
- **L:** 2-4 hours
- **XL:** 4+ hours (should be broken down further)

## Output Format

Save as `tasks.md`:

```markdown
# Task Breakdown

## Summary
- **Total Tasks:** [count]
- **P1 (Urgent):** [count]
- **P2 (High):** [count]
- **P3 (Medium):** [count]
- **P4 (Low):** [count]

---

## Phase 1: Foundation

### TASK-001: Initialize Project Repository
**Priority:** P1 (Urgent)
**Complexity:** S
**Dependencies:** None
**Blocks:** TASK-002, TASK-003

**Description:**
Set up the project with the chosen framework, initialize git repository,
configure package.json/pyproject.toml, and create basic directory structure.

**Acceptance Criteria:**
- [ ] Project initialized with framework CLI
- [ ] Git repository initialized
- [ ] .gitignore configured
- [ ] README.md with setup instructions
- [ ] Basic directory structure created

---

### TASK-002: Configure Development Environment
**Priority:** P1 (Urgent)
**Complexity:** M
**Dependencies:** TASK-001
**Blocks:** TASK-004, TASK-005

**Description:**
Set up linting, formatting, and development tooling.

**Acceptance Criteria:**
- [ ] ESLint/Ruff configured
- [ ] Prettier/Black configured
- [ ] Pre-commit hooks set up
- [ ] VS Code settings (if applicable)
- [ ] npm scripts / Makefile commands defined

---

## Phase 2: Data Layer

### TASK-010: Design Database Schema
**Priority:** P1 (Urgent)
**Complexity:** L
**Dependencies:** TASK-001
**Blocks:** TASK-011, TASK-012

**Description:**
Create the database schema based on the data models in architecture.md.

**Acceptance Criteria:**
- [ ] All entities defined
- [ ] Relationships established
- [ ] Indexes created
- [ ] Migration files generated
- [ ] Schema can be applied to fresh database

---

[Continue for ALL tasks...]

## Phase 3: Backend Core
[Tasks...]

## Phase 4: Frontend Core
[Tasks...]

## Phase 5: Integration
[Tasks...]

## Phase 6: Feature Implementation
[Tasks for each feature...]

## Phase 7: Testing
[Test tasks...]

## Phase 8: Polish & Optimization
[Final tasks...]

---

## Dependency Graph

```
TASK-001 (Project Setup)
    ├── TASK-002 (Dev Environment)
    │   ├── TASK-004 (Backend Setup)
    │   └── TASK-005 (Frontend Setup)
    └── TASK-010 (Database Schema)
        └── TASK-011 (Database Models)
```

## Implementation Order (Suggested)

1. TASK-001, TASK-002 (Foundation)
2. TASK-010, TASK-011, TASK-012 (Data Layer)
3. TASK-020, TASK-021 (Backend Core)
4. [...]
```

## Important Notes

- Generate AT LEAST {{MIN_TASKS}} tasks
- No task should take more than 4 hours
- Every task must have acceptance criteria
- Dependencies must form a valid DAG (no cycles)
- First few tasks should be P1 to establish foundation
- Features should generally be P2
- Polish/optimization should be P3-P4
