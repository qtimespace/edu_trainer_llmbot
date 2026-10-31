"""initial: учётки, группа, присутствие, LLM, агенты, уроки, задания

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    login TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
    active BOOLEAN NOT NULL DEFAULT true,
    must_change_password BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX accounts_login ON accounts (lower(login));
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL UNIQUE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL, ip TEXT NOT NULL DEFAULT '', user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX sessions_account ON sessions (account_id);
CREATE TABLE login_attempts (login TEXT NOT NULL, ip TEXT NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX login_attempts_at ON login_attempts (at);

CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    size INT NOT NULL CHECK (size BETWEEN 2 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE group_students (
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    account_id UUID NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
    seat INT NOT NULL CHECK (seat BETWEEN 1 AND 5),
    note TEXT NOT NULL DEFAULT '',
    budget_usd NUMERIC(10,4) NOT NULL DEFAULT 1.0,
    lesson_password TEXT NOT NULL,
    PRIMARY KEY (group_id, seat)
);
CREATE TABLE presence (
    account_id UUID PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE llm_keys (
    provider TEXT PRIMARY KEY, secret TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE llm_models (
    key TEXT PRIMARY KEY, spec JSONB NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, model_key TEXT,
    input_tokens INT NOT NULL, output_tokens INT NOT NULL, cost_usd NUMERIC(10,4) NOT NULL,
    agent TEXT NOT NULL, task_id TEXT NOT NULL, user_id TEXT, project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ledger_user_time ON ledger (user_id, created_at DESC);
CREATE INDEX ledger_user_model_time ON ledger (user_id, model_key, created_at DESC);
CREATE INDEX ledger_user_provider_time ON ledger (user_id, provider, created_at DESC);
CREATE TABLE llm_cooldowns (
    user_id TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL CHECK (scope IN ('model', 'provider')), key TEXT NOT NULL,
    until TIMESTAMPTZ NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, scope, key)
);

CREATE TABLE agents (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('methodist', 'tutor')),
    system_prompt TEXT NOT NULL DEFAULT '',
    route JSONB NOT NULL DEFAULT '[]',
    max_usd_per_call NUMERIC(10,4) NOT NULL DEFAULT 0.05,
    enabled BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    position INT NOT NULL DEFAULT 0,
    prep_status TEXT NOT NULL DEFAULT 'idle' CHECK (prep_status IN ('idle', 'running', 'failed')),
    prep_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    agent_key TEXT NOT NULL REFERENCES agents(key),
    title TEXT NOT NULL, statement TEXT NOT NULL DEFAULT '',
    checks JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'todo', 'in_progress', 'waiting_student', 'done')),
    position INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tasks_student ON tasks (student_id, status);
CREATE TABLE task_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author TEXT NOT NULL CHECK (author IN ('student', 'agent', 'system')),
    agent_key TEXT, text TEXT NOT NULL, meta JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX task_messages_task ON task_messages (task_id, created_at);
CREATE TABLE agent_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    lesson_id UUID REFERENCES lessons(id) ON DELETE CASCADE,
    student_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    agent_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX agent_jobs_one_running ON agent_jobs (task_id) WHERE status = 'running';
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute("DROP TABLE agent_jobs, task_messages, tasks, lessons, agents, llm_cooldowns, ledger, llm_models, "
               "llm_keys, presence, group_students, groups, login_attempts, sessions, accounts")
