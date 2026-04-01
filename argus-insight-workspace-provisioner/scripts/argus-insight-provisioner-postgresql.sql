-- ============================================================================
-- Argus Insight Workspace Provisioner - PostgreSQL Schema
-- ============================================================================
-- Database: PostgreSQL 14+
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. argus_workspaces
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspaces (
    id                  SERIAL          PRIMARY KEY,
    name                VARCHAR(100)    NOT NULL,
    display_name        VARCHAR(255)    NOT NULL,
    description         TEXT            DEFAULT NULL,
    domain              VARCHAR(255)    NOT NULL,
    k8s_cluster         VARCHAR(255)    DEFAULT NULL,
    k8s_namespace       VARCHAR(255)    DEFAULT NULL,
    gitlab_project_id   INTEGER         DEFAULT NULL,
    gitlab_project_url  VARCHAR(500)    DEFAULT NULL,
    minio_endpoint      VARCHAR(500)    DEFAULT NULL,
    minio_console_endpoint VARCHAR(500) DEFAULT NULL,
    minio_default_bucket VARCHAR(255)   DEFAULT NULL,
    airflow_endpoint    VARCHAR(500)    DEFAULT NULL,
    mlflow_endpoint     VARCHAR(500)    DEFAULT NULL,
    kserve_endpoint     VARCHAR(500)    DEFAULT NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'provisioning',
    resource_profile_id INTEGER         DEFAULT NULL,
    created_by          INTEGER         NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_workspaces_name UNIQUE (name),
    CONSTRAINT fk_workspaces_created_by FOREIGN KEY (created_by) REFERENCES argus_users (id)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_status ON argus_workspaces (status);
CREATE INDEX IF NOT EXISTS idx_workspaces_created_by ON argus_workspaces (created_by);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_workspaces_updated_at
    BEFORE UPDATE ON argus_workspaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- 2. argus_workspace_credentials
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspace_credentials (
    workspace_id        INTEGER         NOT NULL,
    gitlab_http_url     VARCHAR(500)    DEFAULT NULL,
    gitlab_ssh_url      VARCHAR(500)    DEFAULT NULL,
    minio_endpoint      VARCHAR(500)    DEFAULT NULL,
    minio_root_user     VARCHAR(255)    DEFAULT NULL,
    minio_root_password VARCHAR(500)    DEFAULT NULL,
    minio_access_key    VARCHAR(255)    DEFAULT NULL,
    minio_secret_key    VARCHAR(500)    DEFAULT NULL,
    airflow_url         VARCHAR(500)    DEFAULT NULL,
    airflow_admin_username VARCHAR(255) DEFAULT NULL,
    airflow_admin_password VARCHAR(500) DEFAULT NULL,
    mlflow_artifact_bucket VARCHAR(255) DEFAULT NULL,
    kserve_endpoint     VARCHAR(500)    DEFAULT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id),
    CONSTRAINT fk_workspace_credentials_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE
);

CREATE OR REPLACE TRIGGER trg_workspace_credentials_updated_at
    BEFORE UPDATE ON argus_workspace_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- 3. argus_workspace_members
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspace_members (
    id              SERIAL          PRIMARY KEY,
    workspace_id    INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'User',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_workspace_members UNIQUE (workspace_id, user_id),
    CONSTRAINT fk_workspace_members_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_members_user FOREIGN KEY (user_id) REFERENCES argus_users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON argus_workspace_members (user_id);

-- (workflow_executions and workflow_step_executions removed — progress is tracked via audit logs)

