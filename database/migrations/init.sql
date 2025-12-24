-- Autonomous Orchestrator Framework - Database Schema
-- ====================================================
-- This file initializes the database schema for Docker deployments.
-- It is run automatically by PostgreSQL on first container start.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    -- Statuses: 'not_started', 'running', 'paused', 'stopping', 'stopped', 'completed', 'failed'
    current_phase VARCHAR(50),
    directory VARCHAR(500),
    config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Pipeline state (one per project)
CREATE TABLE IF NOT EXISTS pipeline_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phases JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_checkpoint TIMESTAMP WITH TIME ZONE,
    heartbeat TIMESTAMP WITH TIME ZONE,
    shutdown_requested BOOLEAN DEFAULT FALSE NOT NULL,
    shutdown_reason VARCHAR(100),
    agent_snapshots JSONB,
    interrupted_work_items JSONB,
    last_successful_step VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    UNIQUE(project_id)
);

-- Work items (features/tasks)
CREATE TABLE IF NOT EXISTS work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'todo',
    -- Statuses: 'todo', 'in_progress', 'done', 'blocked'
    priority INTEGER DEFAULT 3 NOT NULL,
    -- Priority: 1=urgent, 2=high, 3=medium, 4=low
    phase VARCHAR(50),
    parent_id UUID REFERENCES work_items(id),
    dependencies JSONB,
    labels JSONB,
    metadata JSONB,
    external_id VARCHAR(255),
    -- External system ID (e.g., Linear issue ID)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Work item comments (for handoff notes)
CREATE TABLE IF NOT EXISTS work_item_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Phase outputs (stored artifacts)
CREATE TABLE IF NOT EXISTS phase_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,
    output_type VARCHAR(100),
    -- Types: 'requirements', 'architecture', 'features', 'test_results', etc.
    content JSONB,
    file_path VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Session logs (for debugging/audit)
CREATE TABLE IF NOT EXISTS session_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase VARCHAR(50),
    session_number INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50),
    summary TEXT,
    error TEXT,
    tool_calls JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- ============================================
-- INDEXES
-- ============================================

-- Projects
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);

-- Pipeline states
CREATE INDEX IF NOT EXISTS idx_pipeline_states_project ON pipeline_states(project_id);

-- Work items
CREATE INDEX IF NOT EXISTS idx_work_items_project ON work_items(project_id);
CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_priority ON work_items(priority);
CREATE INDEX IF NOT EXISTS idx_work_items_phase ON work_items(phase);
CREATE INDEX IF NOT EXISTS idx_work_items_external_id ON work_items(external_id);

-- Work item comments
CREATE INDEX IF NOT EXISTS idx_work_item_comments_work_item ON work_item_comments(work_item_id);

-- Phase outputs
CREATE INDEX IF NOT EXISTS idx_phase_outputs_project ON phase_outputs(project_id);
CREATE INDEX IF NOT EXISTS idx_phase_outputs_phase ON phase_outputs(phase);

-- Session logs
CREATE INDEX IF NOT EXISTS idx_session_logs_project ON session_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_session_logs_phase ON session_logs(phase);

-- ============================================
-- TRIGGERS for updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to relevant tables
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_projects_updated_at') THEN
        CREATE TRIGGER update_projects_updated_at
            BEFORE UPDATE ON projects
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_pipeline_states_updated_at') THEN
        CREATE TRIGGER update_pipeline_states_updated_at
            BEFORE UPDATE ON pipeline_states
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_work_items_updated_at') THEN
        CREATE TRIGGER update_work_items_updated_at
            BEFORE UPDATE ON work_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ============================================
-- INITIAL DATA (optional)
-- ============================================

-- No initial data needed - projects are created through the API
