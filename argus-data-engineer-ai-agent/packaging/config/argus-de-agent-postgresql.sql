-- Argus Data Engineer AI Agent - PostgreSQL DDL

CREATE TABLE IF NOT EXISTS de_agent_conversations (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL UNIQUE,
    username        VARCHAR(100) NOT NULL DEFAULT 'anonymous',
    title           VARCHAR(500),
    status          VARCHAR(30)  NOT NULL DEFAULT 'active',
    total_steps     INTEGER      NOT NULL DEFAULT 0,
    total_prompt_tokens    INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_username ON de_agent_conversations(username);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON de_agent_conversations(status);

CREATE TABLE IF NOT EXISTS de_agent_messages (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    content         TEXT         NOT NULL,
    step_type       VARCHAR(30),
    tool_name       VARCHAR(100),
    tool_params     TEXT,
    tool_result     TEXT,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON de_agent_messages(session_id);

CREATE TABLE IF NOT EXISTS de_agent_task_logs (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    tool_name       VARCHAR(100) NOT NULL,
    tool_params     TEXT,
    result_success  VARCHAR(10)  NOT NULL DEFAULT 'true',
    result_summary  TEXT,
    approved_by     VARCHAR(100),
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    executed_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_logs_session ON de_agent_task_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_tool ON de_agent_task_logs(tool_name);
