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

-- ---------------------------------------------------------------------------
-- 4. argus_workflow_executions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workflow_executions (
    id              SERIAL          PRIMARY KEY,
    workspace_id    INTEGER         NOT NULL,
    workflow_name   VARCHAR(100)    NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ     DEFAULT NULL,
    finished_at     TIMESTAMPTZ     DEFAULT NULL,
    error_message   TEXT            DEFAULT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_workflow_exec_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_exec_workspace ON argus_workflow_executions (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_exec_status ON argus_workflow_executions (status);

-- ---------------------------------------------------------------------------
-- 5. argus_workflow_step_executions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workflow_step_executions (
    id              SERIAL          PRIMARY KEY,
    execution_id    INTEGER         NOT NULL,
    step_name       VARCHAR(100)    NOT NULL,
    step_order      INTEGER         NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ     DEFAULT NULL,
    finished_at     TIMESTAMPTZ     DEFAULT NULL,
    error_message   TEXT            DEFAULT NULL,
    result_data     TEXT            DEFAULT NULL,
    CONSTRAINT fk_step_exec_execution FOREIGN KEY (execution_id) REFERENCES argus_workflow_executions (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_step_exec_execution ON argus_workflow_step_executions (execution_id);
CREATE INDEX IF NOT EXISTS idx_step_exec_order ON argus_workflow_step_executions (execution_id, step_order);

-- ---------------------------------------------------------------------------
-- 6. argus_pipelines
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_pipelines (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    display_name    VARCHAR(255)    NOT NULL,
    description     TEXT            DEFAULT NULL,
    version         INTEGER         NOT NULL DEFAULT 1,
    deleted         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_by      VARCHAR(100)    DEFAULT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_pipelines_name UNIQUE (name)
);

COMMENT ON TABLE argus_pipelines IS 'Named deployment pipelines for workspace provisioning';
COMMENT ON COLUMN argus_pipelines.name IS 'Unique pipeline slug (e.g. pipeline-20260329-143052-7a3f)';
COMMENT ON COLUMN argus_pipelines.display_name IS 'Human-readable pipeline name';
COMMENT ON COLUMN argus_pipelines.version IS 'Auto-incremented on each save (starts at 1)';
COMMENT ON COLUMN argus_pipelines.deleted IS 'Soft delete flag';
COMMENT ON COLUMN argus_pipelines.created_by IS 'Username of the pipeline creator';

CREATE OR REPLACE TRIGGER trg_pipelines_updated_at
    BEFORE UPDATE ON argus_pipelines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- 7. argus_plugin_configs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_plugin_configs (
    id                SERIAL          PRIMARY KEY,
    pipeline_id       INTEGER         DEFAULT NULL,
    plugin_name       VARCHAR(100)    NOT NULL,
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    display_order     INTEGER         NOT NULL,
    selected_version  VARCHAR(50)     DEFAULT NULL,
    default_config    JSON            DEFAULT NULL,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pipeline_plugin UNIQUE (pipeline_id, plugin_name),
    CONSTRAINT fk_plugin_config_pipeline FOREIGN KEY (pipeline_id) REFERENCES argus_pipelines (id) ON DELETE CASCADE
);

COMMENT ON TABLE argus_plugin_configs IS 'Plugin configuration within a pipeline (order, version, settings)';
COMMENT ON COLUMN argus_plugin_configs.pipeline_id IS 'FK to argus_pipelines (NULL for global/legacy config)';
COMMENT ON COLUMN argus_plugin_configs.plugin_name IS 'Plugin identifier (e.g. airflow-deploy, minio-deploy)';
COMMENT ON COLUMN argus_plugin_configs.display_order IS 'Execution order within the pipeline';
COMMENT ON COLUMN argus_plugin_configs.selected_version IS 'Plugin version (NULL means default)';
COMMENT ON COLUMN argus_plugin_configs.default_config IS 'Plugin config overrides as JSON';

CREATE INDEX IF NOT EXISTS idx_plugin_configs_pipeline ON argus_plugin_configs (pipeline_id);

CREATE OR REPLACE TRIGGER trg_plugin_configs_updated_at
    BEFORE UPDATE ON argus_plugin_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
