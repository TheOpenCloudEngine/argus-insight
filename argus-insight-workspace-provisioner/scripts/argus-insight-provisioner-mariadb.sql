-- ============================================================================
-- Argus Insight Workspace Provisioner - MariaDB Schema
-- ============================================================================
-- Database: MariaDB 10.6+
-- Charset:  utf8mb4 / utf8mb4_unicode_ci
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. argus_workspaces
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspaces (
    id              INT             NOT NULL AUTO_INCREMENT,
    name            VARCHAR(100)    NOT NULL,
    display_name    VARCHAR(255)    NOT NULL,
    description     TEXT            DEFAULT NULL,
    domain          VARCHAR(255)    NOT NULL,
    k8s_cluster     VARCHAR(255)    DEFAULT NULL,
    k8s_namespace   VARCHAR(255)    DEFAULT NULL,
    gitlab_project_id  INT          DEFAULT NULL,
    gitlab_project_url VARCHAR(500) DEFAULT NULL,
    minio_endpoint  VARCHAR(500)    DEFAULT NULL,
    minio_console_endpoint VARCHAR(500) DEFAULT NULL,
    minio_default_bucket VARCHAR(255) DEFAULT NULL,
    airflow_endpoint VARCHAR(500)   DEFAULT NULL,
    mlflow_endpoint VARCHAR(500)    DEFAULT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'provisioning',
    created_by      INT             NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_workspaces_name (name),
    KEY idx_workspaces_status (status),
    KEY idx_workspaces_created_by (created_by),
    CONSTRAINT fk_workspaces_created_by FOREIGN KEY (created_by) REFERENCES argus_users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 2. argus_workspace_credentials
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspace_credentials (
    workspace_id        INT             NOT NULL,
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
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id),
    CONSTRAINT fk_workspace_credentials_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 3. argus_workspace_members
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workspace_members (
    id              INT             NOT NULL AUTO_INCREMENT,
    workspace_id    INT             NOT NULL,
    user_id         INT             NOT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'User',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_workspace_members (workspace_id, user_id),
    KEY idx_workspace_members_user (user_id),
    CONSTRAINT fk_workspace_members_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_members_user FOREIGN KEY (user_id) REFERENCES argus_users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 4. argus_workflow_executions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workflow_executions (
    id              INT             NOT NULL AUTO_INCREMENT,
    workspace_id    INT             NOT NULL,
    workflow_name   VARCHAR(100)    NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    started_at      DATETIME        DEFAULT NULL,
    finished_at     DATETIME        DEFAULT NULL,
    error_message   TEXT            DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_workflow_exec_workspace (workspace_id),
    KEY idx_workflow_exec_status (status),
    CONSTRAINT fk_workflow_exec_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 5. argus_workflow_step_executions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_workflow_step_executions (
    id              INT             NOT NULL AUTO_INCREMENT,
    execution_id    INT             NOT NULL,
    step_name       VARCHAR(100)    NOT NULL,
    step_order      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    started_at      DATETIME        DEFAULT NULL,
    finished_at     DATETIME        DEFAULT NULL,
    error_message   TEXT            DEFAULT NULL,
    result_data     TEXT            DEFAULT NULL,
    PRIMARY KEY (id),
    KEY idx_step_exec_execution (execution_id),
    KEY idx_step_exec_order (execution_id, step_order),
    CONSTRAINT fk_step_exec_execution FOREIGN KEY (execution_id) REFERENCES argus_workflow_executions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
