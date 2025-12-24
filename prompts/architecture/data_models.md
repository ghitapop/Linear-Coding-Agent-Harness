# Architecture Phase - Data Models

## Your Task
Design the data models and database schema based on the requirements.

## Requirements
{{REQUIREMENTS}}

## Instructions

### 1. Identify Core Entities

List all entities needed:
- User-related entities (User, Profile, Session)
- Business domain entities
- Supporting entities (Audit logs, Settings)
- Relationship entities (many-to-many joins)

### 2. Define Entity Attributes

For each entity, specify:
- Primary key strategy (UUID, auto-increment, etc.)
- Required vs optional fields
- Data types
- Constraints (unique, not null, etc.)
- Default values

### 3. Define Relationships

Map relationships between entities:
- One-to-One (User ↔ Profile)
- One-to-Many (User → Posts)
- Many-to-Many (Users ↔ Roles)
- Self-referential (Comments → Parent Comment)

### 4. Indexing Strategy

Identify indexes needed for:
- Primary keys
- Foreign keys
- Frequently queried fields
- Full-text search fields
- Composite indexes for common queries

### 5. Data Validation Rules

Define validation for each field:
- String length limits
- Number ranges
- Format validation (email, phone, URL)
- Enum values
- Custom business rules

### 6. Migration Strategy

Plan for:
- Initial schema creation
- Seed data
- Future migrations approach

## Output Format

Create a data models section for `architecture.md`:

```markdown
## Data Models

### Entity Relationship Diagram
```
┌──────────────┐     ┌──────────────┐
│    User      │────<│    Post      │
├──────────────┤     ├──────────────┤
│ id (PK)      │     │ id (PK)      │
│ email        │     │ user_id (FK) │
│ name         │     │ title        │
│ created_at   │     │ content      │
└──────────────┘     └──────────────┘
```

### Entity: User
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email |
| name | VARCHAR(100) | NOT NULL | Display name |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt hash |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update |

**Indexes:**
- `idx_users_email` on `email` (unique)
- `idx_users_created_at` on `created_at`

**Validation:**
- email: Valid email format
- name: 1-100 characters
- password: Min 8 chars before hashing

### Entity: Post
[Similar structure...]

### Relationships
| From | To | Type | Description |
|------|-----|------|-------------|
| User | Post | 1:N | User creates many posts |
| Post | Comment | 1:N | Post has many comments |

### Database Schema (SQL)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

### TypeScript Types
```typescript
interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
}
```
```

Focus on creating a complete, consistent data model that supports all requirements.
