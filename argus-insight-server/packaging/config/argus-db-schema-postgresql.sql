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
('k8s', 'k8s_kubeconfig_path',        '/etc/rancher/k3s/k3s.yaml', 'Path to kubeconfig file'),
('k8s', 'k8s_namespace_prefix',       'argus-ws-',                  'Workspace namespace prefix'),
('k8s', 'k8s_context',                '',                           'Kubeconfig context (empty = default)'),
('k8s', 'k8s_monitoring_cache_ttl',   '60',                         'Cluster overview cache TTL in seconds (min 60)'),
('k8s', 'k8s_monitoring_pod_filter',  'argus-*',                    'Pod name glob filter for namespace resource usage'),
-- Image OS Repositories
('repo_debian-11', 'repos', '{"enabled":false,"builtin":[{"type":"deb","url":"http://deb.debian.org/debian","dist":"bullseye","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://deb.debian.org/debian","dist":"bullseye-updates","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://security.debian.org/debian-security","dist":"bullseye-security","components":"main","enabled":true,"trusted":false}],"custom":[]}', 'Package repositories for debian-11'),
('repo_debian-12', 'repos', '{"enabled":false,"builtin":[{"type":"deb","url":"http://deb.debian.org/debian","dist":"bookworm","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://deb.debian.org/debian","dist":"bookworm-updates","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://security.debian.org/debian-security","dist":"bookworm-security","components":"main","enabled":true,"trusted":false}],"custom":[]}', 'Package repositories for debian-12'),
('repo_debian-13', 'repos', '{"enabled":false,"builtin":[{"type":"deb","url":"http://deb.debian.org/debian","dist":"trixie","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://deb.debian.org/debian","dist":"trixie-updates","components":"main","enabled":true,"trusted":false},{"type":"deb","url":"http://security.debian.org/debian-security","dist":"trixie-security","components":"main","enabled":true,"trusted":false}],"custom":[]}', 'Package repositories for debian-13'),
('repo_ubuntu-22.04', 'repos', '{"enabled":false,"builtin":[{"type":"deb","url":"http://archive.ubuntu.com/ubuntu","dist":"jammy","components":"main restricted universe","enabled":true,"trusted":false},{"type":"deb","url":"http://archive.ubuntu.com/ubuntu","dist":"jammy-updates","components":"main restricted universe","enabled":true,"trusted":false},{"type":"deb","url":"http://security.ubuntu.com/ubuntu","dist":"jammy-security","components":"main restricted universe","enabled":true,"trusted":false}],"custom":[]}', 'Package repositories for ubuntu-22.04'),
('repo_ubuntu-24.04', 'repos', '{"enabled":false,"builtin":[{"type":"deb","url":"http://archive.ubuntu.com/ubuntu","dist":"noble","components":"main restricted universe","enabled":true,"trusted":false},{"type":"deb","url":"http://archive.ubuntu.com/ubuntu","dist":"noble-updates","components":"main restricted universe","enabled":true,"trusted":false},{"type":"deb","url":"http://security.ubuntu.com/ubuntu","dist":"noble-security","components":"main restricted universe","enabled":true,"trusted":false}],"custom":[]}', 'Package repositories for ubuntu-24.04'),
('repo_rhel-10', 'repos', '{"enabled":false,"builtin":[{"repo_id":"baseos","name":"RHEL 10 BaseOS","baseurl":"https://cdn.redhat.com/content/dist/rhel10/$releasever/$basearch/baseos/os/","gpgcheck":true,"enabled":true},{"repo_id":"appstream","name":"RHEL 10 AppStream","baseurl":"https://cdn.redhat.com/content/dist/rhel10/$releasever/$basearch/appstream/os/","gpgcheck":true,"enabled":true}],"custom":[]}', 'Package repositories for rhel-10'),
('repo_rocky-9', 'repos', '{"enabled":false,"builtin":[{"repo_id":"baseos","name":"Rocky Linux $releasever - BaseOS","baseurl":"http://dl.rockylinux.org/pub/rocky/$releasever/BaseOS/$basearch/os/","gpgcheck":true,"enabled":true},{"repo_id":"appstream","name":"Rocky Linux $releasever - AppStream","baseurl":"http://dl.rockylinux.org/pub/rocky/$releasever/AppStream/$basearch/os/","gpgcheck":true,"enabled":true},{"repo_id":"extras","name":"Rocky Linux $releasever - Extras","baseurl":"http://dl.rockylinux.org/pub/rocky/$releasever/extras/$basearch/os/","gpgcheck":true,"enabled":true}],"custom":[]}', 'Package repositories for rocky-9'),
('repo_alpine-3.20', 'repos', '{"enabled":false,"builtin":[{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.20/main","enabled":true},{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.20/community","enabled":true}],"custom":[]}', 'Package repositories for alpine-3.20'),
('repo_alpine-3.21', 'repos', '{"enabled":false,"builtin":[{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.21/main","enabled":true},{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.21/community","enabled":true}],"custom":[]}', 'Package repositories for alpine-3.21')
ON CONFLICT (config_key) DO NOTHING;

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
    service_id      VARCHAR(20),
    display_name    VARCHAR(255),
    version         VARCHAR(50),
    endpoint        VARCHAR(500),
    username        VARCHAR(255),
    password        VARCHAR(255),
    access_token    VARCHAR(500),
    status          VARCHAR(20)     NOT NULL DEFAULT 'running',
    metadata        JSON,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_workspace_services IS 'Service instances deployed to a workspace (multi-instance for vscode/jupyter)';
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

-- ---------------------------------------------------------------------------
-- Resource Profiles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS argus_resource_profiles (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    display_name    VARCHAR(255)    NOT NULL,
    description     TEXT,
    cpu_cores       NUMERIC(10,3)   NOT NULL,
    memory_mb       BIGINT          NOT NULL,
    is_default      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Enforce at most one default profile
CREATE UNIQUE INDEX IF NOT EXISTS idx_resource_profiles_default
    ON argus_resource_profiles (is_default) WHERE is_default = TRUE;

CREATE OR REPLACE TRIGGER trg_resource_profiles_updated_at
    BEFORE UPDATE ON argus_resource_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE argus_resource_profiles IS 'Resource profiles defining CPU/Memory limits for workspaces';
COMMENT ON COLUMN argus_resource_profiles.cpu_cores IS 'Total CPU cores (e.g. 8.000)';
COMMENT ON COLUMN argus_resource_profiles.memory_mb IS 'Total memory in MiB (e.g. 16384 for 16 GiB)';
COMMENT ON COLUMN argus_resource_profiles.is_default IS 'Default profile for new workspaces (at most one)';

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


-- ---------------------------------------------------------------------------
-- VOC (Voice of Customer) tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_voc_issues (
    id                  SERIAL          PRIMARY KEY,
    title               VARCHAR(300)    NOT NULL,
    description         TEXT            NOT NULL,
    category            VARCHAR(30)     NOT NULL DEFAULT 'general',
    priority            VARCHAR(20)     NOT NULL DEFAULT 'medium',
    status              VARCHAR(20)     NOT NULL DEFAULT 'open',
    author_user_id      INTEGER         NOT NULL,
    author_username     VARCHAR(100),
    assignee_user_id    INTEGER,
    assignee_username   VARCHAR(100),
    workspace_id        INTEGER,
    workspace_name      VARCHAR(100),
    service_id          INTEGER,
    service_name        VARCHAR(100),
    resource_detail     JSONB,
    resolved_at         TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE TRIGGER trg_voc_issues_updated_at
    BEFORE UPDATE ON argus_voc_issues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE argus_voc_issues IS 'VOC (Voice of Customer) issue tracker';
COMMENT ON COLUMN argus_voc_issues.category IS 'resource_request | service_issue | feature_request | account | general';
COMMENT ON COLUMN argus_voc_issues.priority IS 'critical | high | medium | low';
COMMENT ON COLUMN argus_voc_issues.status IS 'open | in_progress | resolved | rejected | closed';

CREATE TABLE IF NOT EXISTS argus_voc_comments (
    id                  SERIAL          PRIMARY KEY,
    issue_id            INTEGER         NOT NULL,
    parent_id           INTEGER,
    author_user_id      INTEGER         NOT NULL,
    author_username     VARCHAR(100),
    body                TEXT            NOT NULL,
    body_plain          TEXT,
    is_system           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voc_comments_issue_id ON argus_voc_comments (issue_id);

CREATE OR REPLACE TRIGGER trg_voc_comments_updated_at
    BEFORE UPDATE ON argus_voc_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE argus_voc_comments IS 'Comments on VOC issues (user or system-generated)';
COMMENT ON COLUMN argus_voc_comments.is_system IS 'True for auto-generated status-change comments';
COMMENT ON COLUMN argus_voc_comments.is_deleted IS 'Soft-delete flag';


-- ---------------------------------------------------------------------------
-- ML Studio tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_ml_pipelines (
    id                  SERIAL          PRIMARY KEY,
    workspace_id        INTEGER         NOT NULL,
    name                VARCHAR(255)    NOT NULL,
    description         TEXT            DEFAULT '',
    pipeline_json       JSONB           NOT NULL,
    author_user_id      INTEGER         NOT NULL,
    author_username     VARCHAR(100),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_pipelines_workspace_id ON argus_ml_pipelines (workspace_id);

CREATE OR REPLACE TRIGGER trg_ml_pipelines_updated_at
    BEFORE UPDATE ON argus_ml_pipelines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE argus_ml_pipelines IS 'Saved ML pipeline DAGs from the Modeler';
COMMENT ON COLUMN argus_ml_pipelines.pipeline_json IS 'Serialized DAG: {nodes, edges, viewport, idCounter}';

CREATE TABLE IF NOT EXISTS argus_ml_jobs (
    id                  SERIAL          PRIMARY KEY,
    workspace_id        INTEGER         NOT NULL,
    name                VARCHAR(255)    NOT NULL,
    source              VARCHAR(20)     NOT NULL DEFAULT 'wizard',
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending',
    task_type           VARCHAR(30)     NOT NULL,
    target_column       VARCHAR(255)    NOT NULL DEFAULT '',
    metric              VARCHAR(50)     NOT NULL DEFAULT 'auto',
    algorithm           VARCHAR(50)     NOT NULL DEFAULT 'auto',
    data_source         JSONB           NOT NULL DEFAULT '{}',
    config              JSONB,
    results             JSONB,
    error_message       TEXT,
    progress            INTEGER         NOT NULL DEFAULT 0,
    pipeline_id         INTEGER,
    generated_code      TEXT,
    author_user_id      INTEGER         NOT NULL,
    author_username     VARCHAR(100),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ml_jobs_workspace_id ON argus_ml_jobs (workspace_id);

CREATE OR REPLACE TRIGGER trg_ml_jobs_updated_at
    BEFORE UPDATE ON argus_ml_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE argus_ml_jobs IS 'ML training/pipeline execution jobs';
COMMENT ON COLUMN argus_ml_jobs.source IS 'wizard | modeler';
COMMENT ON COLUMN argus_ml_jobs.status IS 'pending | running | completed | failed | cancelled';
COMMENT ON COLUMN argus_ml_jobs.pipeline_id IS 'Linked pipeline ID (modeler only)';
COMMENT ON COLUMN argus_ml_jobs.generated_code IS 'Generated Python code (modeler only)';
