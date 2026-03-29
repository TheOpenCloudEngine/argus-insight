-- Argus Insight Server - PostgreSQL Database and User Setup
-- Run this script as a PostgreSQL superuser (e.g., postgres)
--
-- Usage:
--   sudo -u postgres psql -f argus-db-schema-postgresql.sql

-- Create user
CREATE USER argus WITH PASSWORD 'argus';

-- Create database
CREATE DATABASE argus OWNER = argus;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE argus TO argus;

-- Connect to the argus database and set up schema permissions
\c argus

GRANT ALL PRIVILEGES ON SCHEMA public TO argus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO argus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO argus;

CREATE TABLE IF NOT EXISTS argus_agents (
    hostname        VARCHAR(255)    PRIMARY KEY,
    ip_address      VARCHAR(45)     NOT NULL,
    version         VARCHAR(50),
    kernel_version  VARCHAR(255),
    os_version      VARCHAR(255),
    cpu_count       INTEGER,
    core_count      INTEGER,
    total_memory    BIGINT,
    cpu_usage       DOUBLE PRECISION,
    memory_usage    DOUBLE PRECISION,
    disk_swap_percent DOUBLE PRECISION,
    status          VARCHAR(20)     NOT NULL DEFAULT 'UNREGISTERED',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE argus_agents IS 'Agent master table storing identity and latest resource usage';
COMMENT ON COLUMN argus_agents.hostname IS 'Agent hostname (unique identifier)';
COMMENT ON COLUMN argus_agents.ip_address IS 'Agent IP address (IPv4/IPv6)';
COMMENT ON COLUMN argus_agents.version IS 'Agent software version';
COMMENT ON COLUMN argus_agents.kernel_version IS 'OS kernel version';
COMMENT ON COLUMN argus_agents.os_version IS 'OS distribution and version';
COMMENT ON COLUMN argus_agents.cpu_count IS 'Logical CPU count';
COMMENT ON COLUMN argus_agents.core_count IS 'Physical core count';
COMMENT ON COLUMN argus_agents.total_memory IS 'Total memory in bytes';
COMMENT ON COLUMN argus_agents.cpu_usage IS 'Total CPU usage percentage (0.0-100.0)';
COMMENT ON COLUMN argus_agents.memory_usage IS 'Total memory usage percentage (0.0-100.0)';
COMMENT ON COLUMN argus_agents.disk_swap_percent IS 'Disk swap usage percentage (0.0-100.0)';
COMMENT ON COLUMN argus_agents.status IS 'UNREGISTERED | REGISTERED | DISCONNECTED';

CREATE TABLE IF NOT EXISTS argus_agents_heartbeat (
    hostname            VARCHAR(255)    PRIMARY KEY,
    last_heartbeat_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE argus_agents_heartbeat IS 'Tracks the last heartbeat timestamp per agent';
COMMENT ON COLUMN argus_agents_heartbeat.hostname IS 'Agent hostname (references argus_agents)';
COMMENT ON COLUMN argus_agents_heartbeat.last_heartbeat_at IS 'Timestamp of the last heartbeat received';

-- ---------------------------------------------------------------------------
-- User management tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id          SERIAL          PRIMARY KEY,
    role_id     VARCHAR(50)     NOT NULL UNIQUE,
    name        VARCHAR(50)     NOT NULL,
    description VARCHAR(255),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_roles IS 'Role master table defining available user roles';
COMMENT ON COLUMN argus_roles.id IS 'Auto-incremented role identifier';
COMMENT ON COLUMN argus_roles.role_id IS 'Unique role identifier matching Keycloak realm role names (e.g. argus-admin)';
COMMENT ON COLUMN argus_roles.name IS 'Display name (e.g. Admin, User)';
COMMENT ON COLUMN argus_roles.description IS 'Human-readable role description';
COMMENT ON COLUMN argus_roles.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN argus_roles.updated_at IS 'Record last update timestamp';

CREATE TABLE IF NOT EXISTS argus_users (
    id              SERIAL          PRIMARY KEY,
    username        VARCHAR(100)    NOT NULL UNIQUE,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    phone_number    VARCHAR(30),
    password_hash   VARCHAR(255)    NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    auth_type       VARCHAR(20)     NOT NULL DEFAULT 'local',
    s3_access_key   VARCHAR(100),
    s3_secret_key   VARCHAR(100),
    s3_bucket       VARCHAR(255),
    gitlab_username VARCHAR(100),
    gitlab_password VARCHAR(255),
    role_id         INTEGER         NOT NULL REFERENCES argus_roles(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_users IS 'User account table for authentication and authorization';
COMMENT ON COLUMN argus_users.id IS 'Auto-incremented user identifier';
COMMENT ON COLUMN argus_users.username IS 'Unique login username';
COMMENT ON COLUMN argus_users.email IS 'Unique email address';
COMMENT ON COLUMN argus_users.first_name IS 'User first name';
COMMENT ON COLUMN argus_users.last_name IS 'User last name';
COMMENT ON COLUMN argus_users.phone_number IS 'User phone number (optional)';
COMMENT ON COLUMN argus_users.password_hash IS 'SHA-256 hashed password (empty for keycloak users)';
COMMENT ON COLUMN argus_users.status IS 'Account status: active | inactive';
COMMENT ON COLUMN argus_users.auth_type IS 'Authentication type: local | keycloak';
COMMENT ON COLUMN argus_users.gitlab_username IS 'GitLab username (e.g. argus-admin)';
COMMENT ON COLUMN argus_users.gitlab_password IS 'GitLab auto-generated password';
COMMENT ON COLUMN argus_users.role_id IS 'Foreign key to argus_roles(id)';
COMMENT ON COLUMN argus_users.created_at IS 'Account creation timestamp';
COMMENT ON COLUMN argus_users.updated_at IS 'Account last update timestamp';

-- ---------------------------------------------------------------------------
-- File Browser configuration tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser (
    id              SERIAL          PRIMARY KEY,
    config_key      VARCHAR(100)    NOT NULL UNIQUE,
    config_value    VARCHAR(255)    NOT NULL,
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_configuration_filebrowser IS 'File Browser global settings (key-value)';
COMMENT ON COLUMN argus_configuration_filebrowser.id IS 'Auto-incremented identifier';
COMMENT ON COLUMN argus_configuration_filebrowser.config_key IS 'Unique setting key';
COMMENT ON COLUMN argus_configuration_filebrowser.config_value IS 'Setting value';
COMMENT ON COLUMN argus_configuration_filebrowser.description IS 'Human-readable description';
COMMENT ON COLUMN argus_configuration_filebrowser.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN argus_configuration_filebrowser.updated_at IS 'Record last update timestamp';

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser_preview (
    id               SERIAL          PRIMARY KEY,
    category         VARCHAR(50)     NOT NULL UNIQUE,
    label            VARCHAR(100)    NOT NULL,
    max_file_size    BIGINT          NOT NULL,
    max_preview_rows INTEGER,
    description      VARCHAR(255),
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_configuration_filebrowser_preview IS 'File Browser per-category preview limits';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.id IS 'Auto-incremented identifier';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.category IS 'Category identifier (e.g. text, csv, image)';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.label IS 'UI display name';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.max_file_size IS 'Maximum preview file size in bytes';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.max_preview_rows IS 'Maximum preview rows for tabular data';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.description IS 'Category description';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN argus_configuration_filebrowser_preview.updated_at IS 'Record last update timestamp';

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser_extension (
    id              SERIAL          PRIMARY KEY,
    preview_id      INTEGER         NOT NULL REFERENCES argus_configuration_filebrowser_preview(id),
    extension       VARCHAR(20)     NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_configuration_filebrowser_extension IS 'File extension to preview category mapping';
COMMENT ON COLUMN argus_configuration_filebrowser_extension.id IS 'Auto-incremented identifier';
COMMENT ON COLUMN argus_configuration_filebrowser_extension.preview_id IS 'Foreign key to preview category';
COMMENT ON COLUMN argus_configuration_filebrowser_extension.extension IS 'File extension without dot (e.g. csv, xlsx)';
COMMENT ON COLUMN argus_configuration_filebrowser_extension.created_at IS 'Record creation timestamp';

-- Seed File Browser global settings
INSERT INTO argus_configuration_filebrowser (config_key, config_value, description) VALUES
('sort_disable_threshold', '300',  'Disable sorting when directory has N or more entries'),
('max_keys_per_page',      '1000', 'Maximum objects per list request'),
('max_delete_keys',        '1000', 'Maximum objects per delete request')
ON CONFLICT (config_key) DO NOTHING;

-- Seed File Browser preview categories
INSERT INTO argus_configuration_filebrowser_preview
    (id, category, label, max_file_size, max_preview_rows, description) VALUES
( 1, 'text',         'Text / Code',     20480,     NULL, 'Text and source code files (20 KB)'),
( 2, 'csv',          'CSV / TSV',       52428800,  NULL, 'Comma/tab-separated value files (50 MB)'),
( 3, 'image',        'Image',           20971520,  NULL, 'Image files (20 MB)'),
( 4, 'pdf',          'PDF',             104857600, NULL, 'PDF documents (100 MB)'),
( 5, 'video',        'Video',           524288000, NULL, 'Video files (500 MB)'),
( 6, 'audio',        'Audio',           104857600, NULL, 'Audio files (100 MB)'),
( 7, 'spreadsheet',  'Spreadsheet',     52428800,  1000, 'Excel spreadsheet files (50 MB, 1000 rows)'),
( 8, 'document',     'Document',        52428800,  NULL, 'Word document files (50 MB)'),
( 9, 'presentation', 'Presentation',    52428800,  NULL, 'PowerPoint files (50 MB)'),
(10, 'data',         'Data (Parquet)',   104857600, 1000, 'Parquet data files (100 MB, 1000 rows)')
ON CONFLICT (category) DO NOTHING;

-- Seed File Browser extension mappings
INSERT INTO argus_configuration_filebrowser_extension (preview_id, extension) VALUES
-- text (id=1)
(1,'py'),(1,'java'),(1,'ipynb'),(1,'c'),(1,'cpp'),(1,'h'),(1,'hpp'),
(1,'html'),(1,'htm'),(1,'css'),(1,'js'),(1,'ts'),(1,'go'),(1,'rs'),
(1,'sh'),(1,'bash'),(1,'zsh'),(1,'json'),(1,'yaml'),(1,'yml'),
(1,'xml'),(1,'ini'),(1,'conf'),(1,'config'),(1,'md'),(1,'log'),(1,'env'),(1,'txt'),
-- csv (id=2)
(2,'csv'),(2,'tsv'),
-- image (id=3)
(3,'jpg'),(3,'jpeg'),(3,'png'),(3,'gif'),(3,'svg'),(3,'webp'),(3,'bmp'),(3,'ico'),(3,'tiff'),
-- pdf (id=4)
(4,'pdf'),
-- video (id=5)
(5,'mp4'),(5,'webm'),(5,'ogg'),(5,'mov'),(5,'m4v'),(5,'avi'),(5,'mkv'),
-- audio (id=6)
(6,'mp3'),(6,'wav'),(6,'m4a'),(6,'flac'),(6,'aac'),(6,'wma'),
-- spreadsheet (id=7)
(7,'xls'),(7,'xlsx'),
-- document (id=8)
(8,'docx'),
-- presentation (id=9)
(9,'pptx'),
-- data (id=10)
(10,'parquet')
ON CONFLICT (extension) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Infrastructure configuration table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_configuration (
    id              SERIAL          PRIMARY KEY,
    category        VARCHAR(50)     NOT NULL,
    config_key      VARCHAR(100)    NOT NULL UNIQUE,
    config_value    VARCHAR(500)    NOT NULL DEFAULT '',
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_configuration IS 'Infrastructure configuration (key-value, grouped by category)';
COMMENT ON COLUMN argus_configuration.category IS 'Category grouping (e.g. domain, powerdns)';
COMMENT ON COLUMN argus_configuration.config_key IS 'Unique setting key';
COMMENT ON COLUMN argus_configuration.config_value IS 'Setting value';
COMMENT ON COLUMN argus_configuration.description IS 'Human-readable description';

-- Seed Infrastructure configuration
INSERT INTO argus_configuration (category, config_key, config_value, description) VALUES
('domain', 'domain_name',    '', 'Domain name for this infrastructure'),
('domain', 'dns_server_1',   '', 'Primary DNS server'),
('domain', 'dns_server_2',   '', 'Secondary DNS server'),
('domain', 'dns_server_3',   '', 'Tertiary DNS server'),
('domain', 'pdns_ip',        '', 'PowerDNS server IP address'),
('domain', 'pdns_port',      '', 'PowerDNS server port'),
('domain', 'pdns_api_key',   'Argus', 'PowerDNS API key'),
('domain', 'pdns_admin_url', '', 'PowerDNS Admin web UI URL'),
('ldap', 'enable_ldap_auth',      'false',             'Enable LDAP authentication'),
('ldap', 'ldap_url',              'ldap://<SERVER>:389','LDAP/AD server URL'),
('ldap', 'enable_ldap_tls',       'false',             'Enable LDAP TLS'),
('ldap', 'ad_domain',             '',                   'Active Directory domain'),
('ldap', 'ldap_bind_user',        '',                   'LDAP bind user DN'),
('ldap', 'ldap_bind_password',    '',                   'LDAP bind password'),
('ldap', 'user_search_base',      '',                   'User search base DN'),
('ldap', 'user_object_class',     'person',             'User object class'),
('ldap', 'user_search_filter',    '',                   'User search filter'),
('ldap', 'user_name_attribute',   'uid',                'User name attribute'),
('ldap', 'group_search_base',     '',                   'Group search base DN'),
('ldap', 'group_object_class',    'posixGroup',         'Group object class'),
('ldap', 'group_search_filter',   '',                   'Group search filter'),
('ldap', 'group_name_attribute',  'cn',                 'Group name attribute'),
('ldap', 'group_member_attribute','memberUid',           'Group member attribute'),
('command', 'openssl_path',      '/usr/bin/openssl',    'Path to OpenSSL binary'),
-- Auth (Keycloak OIDC)
('auth', 'auth_type',                    'local',                'Authentication type (local or keycloak)'),
('auth', 'auth_keycloak_server_url',     'http://localhost:8180','Keycloak server URL'),
('auth', 'auth_keycloak_realm',          'argus',                'Keycloak realm'),
('auth', 'auth_keycloak_client_id',      'argus-client',         'Keycloak client ID'),
('auth', 'auth_keycloak_client_secret',  'argus-client-secret',  'Keycloak client secret'),
('auth', 'auth_keycloak_admin_role',     'argus-admin',          'Admin role name'),
('auth', 'auth_keycloak_superuser_role', 'argus-superuser',      'Superuser role name'),
('auth', 'auth_keycloak_user_role',      'argus-user',           'User role name'),
-- GitLab
('gitlab', 'gitlab_url',                '',                     'GitLab server URL'),
('gitlab', 'gitlab_username',           'root',                 'GitLab admin username'),
('gitlab', 'gitlab_password',           '',                     'GitLab admin password'),
('gitlab', 'gitlab_token',              '',                     'GitLab API private token'),
('gitlab', 'gitlab_group_path',         'workspaces',           'Default group path for workspace projects'),
('gitlab', 'gitlab_default_branch',     'main',                 'Default branch for new projects'),
('gitlab', 'gitlab_project_visibility', 'internal',             'Project visibility (internal, private, public)'),
-- Kubernetes
('k8s', 'k8s_kubeconfig_path',   '/etc/rancher/k3s/k3s.yaml', 'Path to kubeconfig file'),
('k8s', 'k8s_namespace_prefix',  'argus-ws-',                  'Workspace namespace prefix'),
('k8s', 'k8s_context',           '',                           'Kubeconfig context (empty = default)')
ON CONFLICT (config_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Notes tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_notebooks (
    id              SERIAL          PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES argus_users(id) ON DELETE CASCADE,
    title           VARCHAR(255)    NOT NULL,
    description     VARCHAR(500),
    color           VARCHAR(20)     NOT NULL DEFAULT 'default',
    is_pinned       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_notebooks IS 'User notebooks (top-level container for notes)';
COMMENT ON COLUMN argus_notebooks.user_id IS 'Owner user (FK to argus_users)';
COMMENT ON COLUMN argus_notebooks.title IS 'Notebook display title';
COMMENT ON COLUMN argus_notebooks.description IS 'Optional notebook description';
COMMENT ON COLUMN argus_notebooks.color IS 'Theme color identifier (default, blue, green, red, purple, orange)';
COMMENT ON COLUMN argus_notebooks.is_pinned IS 'Whether the notebook is pinned to top';

CREATE TABLE IF NOT EXISTS argus_notebook_sections (
    id              SERIAL          PRIMARY KEY,
    notebook_id     INTEGER         NOT NULL REFERENCES argus_notebooks(id) ON DELETE CASCADE,
    title           VARCHAR(255)    NOT NULL,
    color           VARCHAR(20)     NOT NULL DEFAULT 'default',
    display_order   INTEGER         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_notebook_sections IS 'Sections within a notebook (tab-like grouping)';
COMMENT ON COLUMN argus_notebook_sections.notebook_id IS 'Parent notebook (FK to argus_notebooks)';
COMMENT ON COLUMN argus_notebook_sections.title IS 'Section display title';
COMMENT ON COLUMN argus_notebook_sections.display_order IS 'Sort order within the notebook';

CREATE TABLE IF NOT EXISTS argus_notebook_pages (
    id              SERIAL          PRIMARY KEY,
    section_id      INTEGER         NOT NULL REFERENCES argus_notebook_sections(id) ON DELETE CASCADE,
    title           VARCHAR(255)    NOT NULL,
    content         TEXT            NOT NULL DEFAULT '',
    display_order   INTEGER         NOT NULL DEFAULT 0,
    is_pinned       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_notebook_pages IS 'Pages within a section containing markdown content';
COMMENT ON COLUMN argus_notebook_pages.section_id IS 'Parent section (FK to argus_notebook_sections)';
COMMENT ON COLUMN argus_notebook_pages.title IS 'Page display title';
COMMENT ON COLUMN argus_notebook_pages.content IS 'Markdown content of the page';
COMMENT ON COLUMN argus_notebook_pages.display_order IS 'Sort order within the section';
COMMENT ON COLUMN argus_notebook_pages.is_pinned IS 'Whether the page is pinned to top';

CREATE TABLE IF NOT EXISTS argus_notebook_page_versions (
    id              SERIAL          PRIMARY KEY,
    page_id         INTEGER         NOT NULL REFERENCES argus_notebook_pages(id) ON DELETE CASCADE,
    version         INTEGER         NOT NULL,
    title           VARCHAR(255)    NOT NULL,
    content         TEXT            NOT NULL,
    change_summary  VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (page_id, version)
);

COMMENT ON TABLE argus_notebook_page_versions IS 'Version history snapshots for notebook pages';
COMMENT ON COLUMN argus_notebook_page_versions.page_id IS 'Page this version belongs to (FK to argus_notebook_pages)';
COMMENT ON COLUMN argus_notebook_page_versions.version IS 'Incrementing version number per page';
COMMENT ON COLUMN argus_notebook_page_versions.title IS 'Page title at this version';
COMMENT ON COLUMN argus_notebook_page_versions.content IS 'Full markdown content snapshot';
COMMENT ON COLUMN argus_notebook_page_versions.change_summary IS 'Optional description of what changed';

-- ---------------------------------------------------------------------------
-- App platform tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_apps (
    id                SERIAL          PRIMARY KEY,
    app_type          VARCHAR(50)     NOT NULL UNIQUE,
    display_name      VARCHAR(100)    NOT NULL,
    description       VARCHAR(500),
    icon              VARCHAR(50),
    template_dir      VARCHAR(100)    NOT NULL,
    default_namespace VARCHAR(255)    NOT NULL DEFAULT 'argus-apps',
    hostname_pattern  VARCHAR(255)    NOT NULL DEFAULT 'argus-{app_type}-{username}.argus-insight.{domain}',
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_apps IS 'App catalog — registered deployable app types';
COMMENT ON COLUMN argus_apps.app_type IS 'Unique app identifier (e.g. vscode, jupyter)';
COMMENT ON COLUMN argus_apps.template_dir IS 'K8s manifest template directory name';
COMMENT ON COLUMN argus_apps.hostname_pattern IS 'Hostname pattern with {app_type}, {username}, {domain} placeholders';

CREATE TABLE IF NOT EXISTS argus_app_instances (
    id                SERIAL          PRIMARY KEY,
    instance_id       VARCHAR(8)      NOT NULL UNIQUE,
    app_id            INTEGER         NOT NULL REFERENCES argus_apps(id),
    user_id           INTEGER         NOT NULL REFERENCES argus_users(id),
    username          VARCHAR(100)    NOT NULL,
    app_type          VARCHAR(50)     NOT NULL,
    domain            VARCHAR(255)    NOT NULL,
    k8s_namespace     VARCHAR(255)    NOT NULL,
    hostname          VARCHAR(500)    NOT NULL,
    status            VARCHAR(20)     NOT NULL DEFAULT 'deploying',
    config            TEXT,
    deploy_steps      TEXT,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_app_instances IS 'Running instances of apps (one user can have multiple)';
COMMENT ON COLUMN argus_app_instances.instance_id IS 'Unique 8-char hex ID (UUID4 prefix) used in hostname and K8s resource names';
COMMENT ON COLUMN argus_app_instances.app_type IS 'Denormalized app type for query convenience';
COMMENT ON COLUMN argus_app_instances.status IS 'deploying | running | failed | deleting | deleted';
COMMENT ON COLUMN argus_app_instances.config IS 'App-specific configuration as JSON';
COMMENT ON COLUMN argus_app_instances.deploy_steps IS 'Deployment step progress as JSON array';

-- Workspace-Pipeline association table
CREATE TABLE IF NOT EXISTS argus_workspace_pipelines (
    id              SERIAL          PRIMARY KEY,
    workspace_id    INTEGER         NOT NULL REFERENCES argus_workspaces(id) ON DELETE CASCADE,
    pipeline_id     INTEGER         NOT NULL REFERENCES argus_pipelines(id),
    deploy_order    INTEGER         NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_workspace_pipelines IS 'Many-to-many: workspaces ↔ pipelines with deployment order and status';
COMMENT ON COLUMN argus_workspace_pipelines.deploy_order IS 'Order in which pipelines are deployed (0-based)';
COMMENT ON COLUMN argus_workspace_pipelines.status IS 'pending | running | completed | failed';

CREATE INDEX IF NOT EXISTS idx_ws_pipelines_workspace ON argus_workspace_pipelines(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ws_pipelines_pipeline ON argus_workspace_pipelines(pipeline_id);

-- Workspace audit log
-- Workspace services (deployed plugin instances)
CREATE TABLE IF NOT EXISTS argus_workspace_services (
    id              SERIAL          PRIMARY KEY,
    workspace_id    INTEGER         NOT NULL REFERENCES argus_workspaces(id) ON DELETE CASCADE,
    plugin_name     VARCHAR(100)    NOT NULL,
    display_name    VARCHAR(255),
    version         VARCHAR(50),
    endpoint        VARCHAR(500),
    username        VARCHAR(255),
    password        VARCHAR(255),
    access_token    VARCHAR(500),
    status          VARCHAR(20)     NOT NULL DEFAULT 'running',
    metadata        JSON,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, plugin_name)
);

COMMENT ON TABLE argus_workspace_services IS 'Service instances deployed to a workspace (one per plugin)';
CREATE INDEX IF NOT EXISTS idx_ws_services_workspace ON argus_workspace_services(workspace_id);

-- Workspace audit log
CREATE TABLE IF NOT EXISTS argus_workspace_audit_logs (
    id                SERIAL          PRIMARY KEY,
    workspace_id      INTEGER         NOT NULL,
    workspace_name    VARCHAR(100)    NOT NULL,
    action            VARCHAR(50)     NOT NULL,
    target_user_id    INTEGER,
    target_username   VARCHAR(100),
    actor_user_id     INTEGER,
    actor_username    VARCHAR(100),
    detail            JSON,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_workspace_audit_logs IS 'Audit log for workspace member and lifecycle events';

CREATE INDEX IF NOT EXISTS idx_audit_workspace ON argus_workspace_audit_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON argus_workspace_audit_logs(created_at DESC);

-- Seed default apps
INSERT INTO argus_apps (app_type, display_name, description, icon, template_dir, default_namespace, hostname_pattern) VALUES
('vscode', 'VS Code Server', 'Browser-based VS Code with S3 workspace storage', 'Code', 'vscode', 'argus-apps', 'argus-{app_type}-{instance_id}.{domain}')
ON CONFLICT (app_type) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Plugin pipeline tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_pipelines (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    display_name    VARCHAR(255)    NOT NULL,
    description     TEXT,
    version         INTEGER         NOT NULL DEFAULT 1,
    deleted         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_pipelines IS 'Named deployment pipelines for workspace provisioning';
COMMENT ON COLUMN argus_pipelines.name IS 'Unique pipeline slug (e.g. pipeline-20260329-143052-7a3f)';
COMMENT ON COLUMN argus_pipelines.display_name IS 'Human-readable pipeline name';
COMMENT ON COLUMN argus_pipelines.version IS 'Auto-incremented on each save (starts at 1)';
COMMENT ON COLUMN argus_pipelines.deleted IS 'Soft delete flag';
COMMENT ON COLUMN argus_pipelines.created_by IS 'Username of the pipeline creator';

CREATE TABLE IF NOT EXISTS argus_plugin_configs (
    id                SERIAL          PRIMARY KEY,
    pipeline_id       INTEGER         REFERENCES argus_pipelines(id) ON DELETE CASCADE,
    plugin_name       VARCHAR(100)    NOT NULL,
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    display_order     INTEGER         NOT NULL,
    selected_version  VARCHAR(50),
    default_config    JSON,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pipeline_plugin UNIQUE (pipeline_id, plugin_name)
);

COMMENT ON TABLE argus_plugin_configs IS 'Plugin configuration within a pipeline (order, version, settings)';
COMMENT ON COLUMN argus_plugin_configs.pipeline_id IS 'FK to argus_pipelines (NULL for global/legacy config)';
COMMENT ON COLUMN argus_plugin_configs.plugin_name IS 'Plugin identifier (e.g. airflow-deploy)';
COMMENT ON COLUMN argus_plugin_configs.display_order IS 'Execution order within the pipeline';
COMMENT ON COLUMN argus_plugin_configs.selected_version IS 'Plugin version (NULL means default)';
COMMENT ON COLUMN argus_plugin_configs.default_config IS 'Plugin config overrides as JSON';

-- Seed default roles
INSERT INTO argus_roles (role_id, name, description) VALUES ('argus-admin', 'Admin', 'Administrator with full access') ON CONFLICT (role_id) DO NOTHING;
INSERT INTO argus_roles (role_id, name, description) VALUES ('argus-superuser', 'Superuser', 'Super user with elevated access') ON CONFLICT (role_id) DO NOTHING;
INSERT INTO argus_roles (role_id, name, description) VALUES ('argus-user', 'User', 'Standard user with limited access') ON CONFLICT (role_id) DO NOTHING;

-- Seed default users (password: password123)
TRUNCATE TABLE argus_users RESTART IDENTITY CASCADE;

INSERT INTO argus_users (username, email, first_name, last_name, phone_number, password_hash, status, role_id) VALUES
('admin',       'admin@argus.io',        'Jaeho',     'Kim',    '010-1234-5678', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   1),
('sjpark',      'sjpark@argus.io',       'Sungjin',   'Park',   '010-2345-6789', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   1),
('mhlee',       'mhlee@argus.io',        'Minhye',    'Lee',    '010-3456-7890', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   1),
('ywchoi',      'ywchoi@argus.io',       'Youngwoo',  'Choi',   '010-4567-8901', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('jhhan',       'jhhan@argus.io',        'Jihoon',    'Han',    '010-5678-9012', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('eunseo.jung', 'eunseo.jung@argus.io',  'Eunseo',    'Jung',   '010-6789-0123', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('dwkim',       'dwkim@argus.io',        'Dongwook',  'Kim',    '010-7890-1234', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2),
('hyson',       'hyson@argus.io',        'Hayoung',   'Son',    NULL,            '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('jsyang',      'jsyang@argus.io',       'Jisoo',     'Yang',   '010-8901-2345', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('twyoon',      'twyoon@argus.io',       'Taewon',    'Yoon',   '010-9012-3456', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2),
('solee',       'solee@argus.io',        'Soyeon',    'Lee',    '010-1111-2222', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('jmbaek',      'jmbaek@argus.io',       'Jimin',     'Baek',   '010-3333-4444', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('swshin',      'swshin@argus.io',       'Seungwoo',  'Shin',   NULL,            '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('yjko',        'yjko@argus.io',         'Yujin',     'Ko',     '010-5555-6666', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2),
('hsryu',       'hsryu@argus.io',        'Hyunsoo',   'Ryu',    '010-7777-8888', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('arina.oh',    'arina.oh@argus.io',     'Arina',     'Oh',     '010-9999-0000', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('wjjeon',      'wjjeon@argus.io',       'Woojin',    'Jeon',   '010-1212-3434', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('nayoung.im',  'nayoung.im@argus.io',   'Nayoung',   'Im',     NULL,            '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2),
('hschang',     'hschang@argus.io',      'Hyunseok',  'Chang',  '010-5656-7878', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('minji.kwon',  'minji.kwon@argus.io',   'Minji',     'Kwon',   '010-2424-3535', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('jynam',       'jynam@argus.io',        'Jungyeon',  'Nam',    '010-4646-5757', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('shsong',      'shsong@argus.io',       'Seunghwan', 'Song',   '010-6868-7979', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2),
('yejin.moon',  'yejin.moon@argus.io',   'Yejin',     'Moon',   NULL,            '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('dohyun.lim',  'dohyun.lim@argus.io',   'Dohyun',    'Lim',    '010-8080-9191', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'active',   2),
('subin.hong',  'subin.hong@argus.io',   'Subin',     'Hong',   '010-1010-2020', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2)
ON CONFLICT (username) DO NOTHING;
