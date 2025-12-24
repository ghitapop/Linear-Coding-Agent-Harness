# Architecture Phase - System Design

## Your Task
Design the technical architecture for the application based on the requirements below.

## Requirements
{{REQUIREMENTS}}

## Instructions

### 1. Technology Stack Selection

Choose and justify each technology:

**Frontend:**
- Framework (React, Vue, Next.js, SvelteKit, etc.)
- State management (Redux, Zustand, Pinia, etc.)
- Styling (Tailwind, CSS Modules, styled-components, etc.)
- Build tool (Vite, webpack, turbopack, etc.)

**Backend:**
- Runtime/Framework (Node.js/Express, Python/FastAPI, Go/Gin, etc.)
- API style (REST, GraphQL, tRPC, etc.)

**Database:**
- Primary database (PostgreSQL, MongoDB, SQLite, etc.)
- Caching layer (Redis, in-memory, etc.)
- ORM/Query builder (Prisma, Drizzle, SQLAlchemy, etc.)

**Infrastructure:**
- Hosting (Vercel, Railway, Docker, AWS, etc.)
- CI/CD approach
- Monitoring/logging

### 2. System Architecture

Create a component diagram showing:
- Frontend application structure
- Backend services and their responsibilities
- Database and data flow
- External integrations
- Authentication flow

Use ASCII art or describe the architecture clearly:

```
┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API   │
│   (Next.js)     │     │   (FastAPI)     │
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   PostgreSQL    │
                        └─────────────────┘
```

### 3. Component Structure

Define the major components:
- Frontend components/pages
- Backend modules/services
- Shared utilities
- Third-party integrations

### 4. Security Architecture

Address:
- Authentication mechanism (JWT, sessions, OAuth)
- Authorization model (RBAC, ABAC)
- Data encryption (at rest, in transit)
- Input validation strategy
- CORS configuration

### 5. Project Structure

Define the directory structure:

```
project/
├── frontend/           # Or src/ for monolith
│   ├── components/
│   ├── pages/
│   ├── hooks/
│   └── utils/
├── backend/            # Or api/ for monolith
│   ├── routes/
│   ├── services/
│   ├── models/
│   └── middleware/
├── shared/             # Shared types/utilities
├── tests/
├── docs/
└── docker/
```

## Output Format
Save as `architecture.md`:

```markdown
# Architecture Document

## Technology Stack

### Frontend
| Technology | Choice | Justification |
|------------|--------|---------------|
| Framework | ... | ... |

### Backend
| Technology | Choice | Justification |
|------------|--------|---------------|
| Framework | ... | ... |

### Database
| Technology | Choice | Justification |
|------------|--------|---------------|
| Primary | ... | ... |

## System Architecture
[ASCII diagram or description]

## Component Design

### Frontend Components
| Component | Responsibility |
|-----------|---------------|
| ... | ... |

### Backend Services
| Service | Responsibility |
|---------|---------------|
| ... | ... |

## Data Flow
[Describe how data flows through the system]

## Security Model
- **Authentication:** [approach]
- **Authorization:** [approach]
- **Data Protection:** [approach]

## Directory Structure
```
[Project structure]
```

## Deployment Architecture
[How the application will be deployed]

## Scalability Considerations
[How the system can scale]

## Trade-offs & Decisions
| Decision | Options Considered | Chosen | Why |
|----------|-------------------|--------|-----|
| ... | ... | ... | ... |
```
