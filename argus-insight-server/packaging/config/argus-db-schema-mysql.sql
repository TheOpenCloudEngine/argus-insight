-- Argus Insight Server - MariaDB/MySQL Database and User Setup
-- Run this script as a MariaDB/MySQL superuser (e.g., root)
--
-- Usage:
--   mysql -u root -p < argus-db-schema-mysql.sql

-- Create database
CREATE DATABASE IF NOT EXISTS argus
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Create user and grant privileges
CREATE USER IF NOT EXISTS 'argus'@'localhost' IDENTIFIED BY 'argus';
GRANT ALL PRIVILEGES ON argus.* TO 'argus'@'localhost';

-- For remote access (optional, uncomment if needed)
-- CREATE USER IF NOT EXISTS 'argus'@'%' IDENTIFIED BY 'argus';
-- GRANT ALL PRIVILEGES ON argus.* TO 'argus'@'%';

FLUSH PRIVILEGES;

-- Argus Insight Server - Database Schema (MariaDB / MySQL)
-- Run this script to create the required tables.

CREATE TABLE IF NOT EXISTS argus_agents (
    hostname        VARCHAR(255)    PRIMARY KEY                        COMMENT 'Agent hostname (unique identifier)',
    ip_address      VARCHAR(45)     NOT NULL                           COMMENT 'Agent IP address (IPv4/IPv6)',
    version         VARCHAR(50)                                        COMMENT 'Agent software version',
    kernel_version  VARCHAR(255)                                       COMMENT 'OS kernel version',
    os_version      VARCHAR(255)                                       COMMENT 'OS distribution and version',
    cpu_count       INT                                                COMMENT 'Logical CPU count',
    core_count      INT                                                COMMENT 'Physical core count',
    total_memory    BIGINT                                             COMMENT 'Total memory in bytes',
    cpu_usage       DOUBLE                                             COMMENT 'Total CPU usage percentage (0.0-100.0)',
    memory_usage    DOUBLE                                             COMMENT 'Total memory usage percentage (0.0-100.0)',
    disk_swap_percent DOUBLE                                           COMMENT 'Disk swap usage percentage (0.0-100.0)',
    status          VARCHAR(20)     NOT NULL DEFAULT 'UNREGISTERED'    COMMENT 'UNREGISTERED | REGISTERED | DISCONNECTED',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Agent master table storing identity and latest resource usage';

CREATE TABLE IF NOT EXISTS argus_agents_heartbeat (
    hostname            VARCHAR(255)    PRIMARY KEY    COMMENT 'Agent hostname (references argus_agents)',
    last_heartbeat_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of the last heartbeat received'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Tracks the last heartbeat timestamp per agent';

-- ---------------------------------------------------------------------------
-- User management tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id          INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented role identifier',
    role_id     VARCHAR(50)     NOT NULL UNIQUE           COMMENT 'Unique role identifier matching Keycloak realm role names (e.g. argus-admin)',
    name        VARCHAR(50)     NOT NULL                  COMMENT 'Display name (e.g. Admin, User)',
    description VARCHAR(255)                              COMMENT 'Human-readable role description',
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Role master table defining available user roles';

CREATE TABLE IF NOT EXISTS argus_users (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented user identifier',
    username        VARCHAR(100)    NOT NULL UNIQUE           COMMENT 'Unique login username',
    email           VARCHAR(255)    NOT NULL UNIQUE           COMMENT 'Unique email address',
    first_name      VARCHAR(100)    NOT NULL                  COMMENT 'User first name',
    last_name       VARCHAR(100)    NOT NULL                  COMMENT 'User last name',
    phone_number    VARCHAR(30)                               COMMENT 'User phone number (optional)',
    password_hash   VARCHAR(255)    NOT NULL DEFAULT ''        COMMENT 'SHA-256 hashed password (empty for keycloak users)',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active' COMMENT 'Account status: active | inactive',
    auth_type       VARCHAR(20)     NOT NULL DEFAULT 'local'  COMMENT 'Authentication type: local | keycloak',
    s3_access_key   VARCHAR(100)                              COMMENT 'MinIO per-user access key',
    s3_secret_key   VARCHAR(100)                              COMMENT 'MinIO per-user secret key',
    s3_bucket       VARCHAR(255)                              COMMENT 'MinIO bucket name',
    gitlab_username VARCHAR(100)                              COMMENT 'GitLab username (e.g. argus-admin)',
    gitlab_password VARCHAR(255)                              COMMENT 'GitLab auto-generated password',
    role_id         INT             NOT NULL                  COMMENT 'Foreign key to argus_roles(id)',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Account creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Account last update timestamp',
    CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES argus_roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='User account table for authentication and authorization';

-- ---------------------------------------------------------------------------
-- File Browser configuration tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented identifier',
    config_key      VARCHAR(100)    NOT NULL UNIQUE           COMMENT 'Unique setting key',
    config_value    VARCHAR(255)    NOT NULL                  COMMENT 'Setting value',
    description     VARCHAR(255)                              COMMENT 'Human-readable description',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='File Browser global settings (key-value)';

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser_preview (
    id               INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented identifier',
    category         VARCHAR(50)     NOT NULL UNIQUE           COMMENT 'Category identifier (e.g. text, csv, image)',
    label            VARCHAR(100)    NOT NULL                  COMMENT 'UI display name',
    max_file_size    BIGINT          NOT NULL                  COMMENT 'Maximum preview file size in bytes',
    max_preview_rows INT                                       COMMENT 'Maximum preview rows for tabular data',
    description      VARCHAR(255)                              COMMENT 'Category description',
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='File Browser per-category preview limits';

CREATE TABLE IF NOT EXISTS argus_configuration_filebrowser_extension (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented identifier',
    preview_id      INT             NOT NULL                  COMMENT 'Foreign key to preview category',
    extension       VARCHAR(20)     NOT NULL UNIQUE           COMMENT 'File extension without dot (e.g. csv, xlsx)',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    CONSTRAINT fk_ext_preview FOREIGN KEY (preview_id)
        REFERENCES argus_configuration_filebrowser_preview(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='File extension to preview category mapping';

-- Seed File Browser global settings
INSERT IGNORE INTO argus_configuration_filebrowser (config_key, config_value, description) VALUES
('sort_disable_threshold', '300',  'Disable sorting when directory has N or more entries'),
('max_keys_per_page',      '1000', 'Maximum objects per list request'),
('max_delete_keys',        '1000', 'Maximum objects per delete request');

-- Seed File Browser preview categories
INSERT IGNORE INTO argus_configuration_filebrowser_preview
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
(10, 'data',         'Data (Parquet)',   104857600, 1000, 'Parquet data files (100 MB, 1000 rows)');

-- Seed File Browser extension mappings
INSERT IGNORE INTO argus_configuration_filebrowser_extension (preview_id, extension) VALUES
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
(10,'parquet');

-- ---------------------------------------------------------------------------
-- Infrastructure configuration table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_configuration (
    id              INT             NOT NULL AUTO_INCREMENT PRIMARY KEY,
    category        VARCHAR(50)     NOT NULL                COMMENT 'Category grouping (e.g. domain, powerdns)',
    config_key      VARCHAR(100)    NOT NULL UNIQUE         COMMENT 'Unique setting key',
    config_value    VARCHAR(500)    NOT NULL DEFAULT ''     COMMENT 'Setting value',
    description     VARCHAR(255)                            COMMENT 'Human-readable description',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='Infrastructure configuration (key-value, grouped by category)';

-- Seed Infrastructure configuration
INSERT IGNORE INTO argus_configuration (category, config_key, config_value, description) VALUES
('domain', 'domain_name',    '', 'Domain name for this infrastructure'),
('domain', 'dns_server_1',   '', 'Primary DNS server'),
('domain', 'dns_server_2',   '', 'Secondary DNS server'),
('domain', 'dns_server_3',   '', 'Tertiary DNS server'),
('domain', 'pdns_ip',        '', 'PowerDNS server IP address'),
('domain', 'pdns_port',      '', 'PowerDNS server port'),
('domain', 'pdns_api_key',   'Argus', 'PowerDNS API key'),
('domain', 'pdns_admin_url', '', 'PowerDNS Admin web UI URL'),
('ldap', 'enable_ldap_auth',      'false',              'Enable LDAP authentication'),
('ldap', 'ldap_url',              'ldap://<SERVER>:389', 'LDAP/AD server URL'),
('ldap', 'enable_ldap_tls',       'false',              'Enable LDAP TLS'),
('ldap', 'ad_domain',             '',                    'Active Directory domain'),
('ldap', 'ldap_bind_user',        '',                    'LDAP bind user DN'),
('ldap', 'ldap_bind_password',    '',                    'LDAP bind password'),
('ldap', 'user_search_base',      '',                    'User search base DN'),
('ldap', 'user_object_class',     'person',              'User object class'),
('ldap', 'user_search_filter',    '',                    'User search filter'),
('ldap', 'user_name_attribute',   'uid',                 'User name attribute'),
('ldap', 'group_search_base',     '',                    'Group search base DN'),
('ldap', 'group_object_class',    'posixGroup',          'Group object class'),
('ldap', 'group_search_filter',   '',                    'Group search filter'),
('ldap', 'group_name_attribute',  'cn',                  'Group name attribute'),
('ldap', 'group_member_attribute','memberUid',            'Group member attribute'),
('command', 'openssl_path',      '/usr/bin/openssl',     'Path to OpenSSL binary'),
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
('repo_alpine-3.21', 'repos', '{"enabled":false,"builtin":[{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.21/main","enabled":true},{"url":"https://dl-cdn.alpinelinux.org/alpine/v3.21/community","enabled":true}],"custom":[]}', 'Package repositories for alpine-3.21');

-- ---------------------------------------------------------------------------
-- App platform tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_apps (
    id                INT             AUTO_INCREMENT PRIMARY KEY,
    app_type          VARCHAR(50)     NOT NULL UNIQUE           COMMENT 'Unique app identifier (e.g. vscode)',
    display_name      VARCHAR(100)    NOT NULL                  COMMENT 'Display name',
    description       VARCHAR(500)                              COMMENT 'Description',
    icon              VARCHAR(50)                               COMMENT 'Lucide icon name',
    template_dir      VARCHAR(100)    NOT NULL                  COMMENT 'K8s template directory name',
    default_namespace VARCHAR(255)    NOT NULL DEFAULT 'argus-apps' COMMENT 'Default K8s namespace',
    hostname_pattern  VARCHAR(255)    NOT NULL DEFAULT 'argus-{app_type}-{username}.argus-insight.{domain}' COMMENT 'Hostname pattern',
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE     COMMENT 'Whether the app is enabled',
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='App catalog - registered deployable app types';

CREATE TABLE IF NOT EXISTS argus_app_instances (
    id                INT             AUTO_INCREMENT PRIMARY KEY,
    instance_id       VARCHAR(8)      NOT NULL UNIQUE           COMMENT 'Unique 8-char hex ID for hostname and K8s resources',
    app_id            INT             NOT NULL                  COMMENT 'FK to argus_apps',
    user_id           INT             NOT NULL                  COMMENT 'FK to argus_users',
    username          VARCHAR(100)    NOT NULL,
    app_type          VARCHAR(50)     NOT NULL                  COMMENT 'Denormalized app type',
    domain            VARCHAR(255)    NOT NULL,
    k8s_namespace     VARCHAR(255)    NOT NULL,
    hostname          VARCHAR(500)    NOT NULL,
    status            VARCHAR(20)     NOT NULL DEFAULT 'deploying' COMMENT 'deploying|running|failed|deleting|deleted',
    config            TEXT                                      COMMENT 'App-specific config as JSON',
    deploy_steps      TEXT                                      COMMENT 'Deployment step progress as JSON array',
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_instance_app FOREIGN KEY (app_id) REFERENCES argus_apps(id),
    CONSTRAINT fk_instance_user FOREIGN KEY (user_id) REFERENCES argus_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Running instances of apps (one user can have multiple)';

-- Workspace-Pipeline association table
CREATE TABLE IF NOT EXISTS argus_workspace_pipelines (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    workspace_id    INT             NOT NULL                  COMMENT 'FK to argus_workspaces',
    pipeline_id     INT             NOT NULL                  COMMENT 'FK to argus_pipelines',
    deploy_order    INT             NOT NULL DEFAULT 0        COMMENT 'Deployment order (0-based)',
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending' COMMENT 'pending|running|completed|failed',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_ws_pipelines_workspace (workspace_id),
    KEY idx_ws_pipelines_pipeline (pipeline_id),
    CONSTRAINT fk_ws_pipeline_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_ws_pipeline_pipeline FOREIGN KEY (pipeline_id) REFERENCES argus_pipelines(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Many-to-many: workspaces to pipelines with deployment order and status';

-- Workspace audit log
-- Workspace services (deployed plugin instances)
CREATE TABLE IF NOT EXISTS argus_workspace_services (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    workspace_id    INT             NOT NULL,
    plugin_name     VARCHAR(100)    NOT NULL,
    service_id      VARCHAR(20)     COMMENT 'Unique service ID used in external hostname',
    display_name    VARCHAR(255),
    version         VARCHAR(50),
    endpoint        VARCHAR(500),
    username        VARCHAR(255),
    password        VARCHAR(255),
    access_token    VARCHAR(500),
    status          VARCHAR(20)     NOT NULL DEFAULT 'running' COMMENT 'running|stopped|failed',
    metadata        JSON,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_ws_services_workspace (workspace_id),
    CONSTRAINT fk_ws_service_workspace FOREIGN KEY (workspace_id) REFERENCES argus_workspaces(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Service instances deployed to a workspace (multi-instance for vscode/jupyter)';

-- Workspace audit log
CREATE TABLE IF NOT EXISTS argus_workspace_audit_logs (
    id                INT             AUTO_INCREMENT PRIMARY KEY,
    workspace_id      INT             NOT NULL,
    workspace_name    VARCHAR(100)    NOT NULL,
    action            VARCHAR(50)     NOT NULL                  COMMENT 'workspace_created|workspace_deleted|member_added|member_removed',
    target_user_id    INT,
    target_username   VARCHAR(100),
    actor_user_id     INT,
    actor_username    VARCHAR(100),
    detail            JSON,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_audit_workspace (workspace_id),
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Audit log for workspace member and lifecycle events';

-- Seed default apps
INSERT IGNORE INTO argus_apps (app_type, display_name, description, icon, template_dir, default_namespace, hostname_pattern) VALUES
('vscode', 'VS Code Server', 'Browser-based VS Code with S3 workspace storage', 'Code', 'vscode', 'argus-apps', 'argus-{app_type}-{instance_id}.{domain}');

-- ---------------------------------------------------------------------------
-- Plugin pipeline tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_pipelines (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE              COMMENT 'Unique pipeline slug (e.g. ml-team-pipeline)',
    display_name    VARCHAR(255)    NOT NULL                     COMMENT 'Human-readable pipeline name',
    description     TEXT                                         COMMENT 'Optional pipeline description',
    version         INT             NOT NULL DEFAULT 1             COMMENT 'Auto-incremented on each save',
    deleted         BOOLEAN         NOT NULL DEFAULT FALSE         COMMENT 'Soft delete flag',
    created_by      VARCHAR(100)                                   COMMENT 'Username of the pipeline creator',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Named deployment pipelines for workspace provisioning';

CREATE TABLE IF NOT EXISTS argus_plugin_configs (
    id                INT             AUTO_INCREMENT PRIMARY KEY,
    pipeline_id       INT                                        COMMENT 'FK to argus_pipelines (NULL for global/legacy config)',
    plugin_name       VARCHAR(100)    NOT NULL                   COMMENT 'Plugin identifier (e.g. airflow-deploy)',
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE      COMMENT 'Whether the plugin is enabled',
    display_order     INT             NOT NULL                   COMMENT 'Execution order within the pipeline',
    selected_version  VARCHAR(50)                                COMMENT 'Plugin version (NULL means default)',
    default_config    JSON                                       COMMENT 'Plugin config overrides as JSON',
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_pipeline_plugin (pipeline_id, plugin_name),
    CONSTRAINT fk_plugin_config_pipeline FOREIGN KEY (pipeline_id) REFERENCES argus_pipelines(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Plugin configuration within a pipeline (order, version, settings)';

-- ---------------------------------------------------------------------------
-- Resource Profiles
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_resource_profiles (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE              COMMENT 'Unique profile slug (e.g. small, medium, large)',
    display_name    VARCHAR(255)    NOT NULL                     COMMENT 'Human-readable profile name',
    description     TEXT                                         COMMENT 'Optional profile description',
    cpu_cores       DECIMAL(10,3)   NOT NULL                     COMMENT 'Total CPU cores (e.g. 8.000)',
    memory_mb       BIGINT          NOT NULL                     COMMENT 'Total memory in MiB (e.g. 16384 for 16 GiB)',
    is_default      BOOLEAN         NOT NULL DEFAULT FALSE       COMMENT 'Default profile for new workspaces',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Resource profiles defining CPU/Memory limits for workspaces';

-- Seed default roles
INSERT IGNORE INTO argus_roles (role_id, name, description) VALUES ('argus-admin', 'Admin', 'Administrator with full access');
INSERT IGNORE INTO argus_roles (role_id, name, description) VALUES ('argus-superuser', 'Superuser', 'Super user with elevated access');
INSERT IGNORE INTO argus_roles (role_id, name, description) VALUES ('argus-user', 'User', 'Standard user with limited access');

-- Seed default users (password: password123)
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE argus_users;
SET FOREIGN_KEY_CHECKS = 1;

INSERT IGNORE INTO argus_users (username, email, first_name, last_name, phone_number, password_hash, status, role_id) VALUES
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
('subin.hong',  'subin.hong@argus.io',   'Subin',     'Hong',   '010-1010-2020', '$2b$12$LJ3m4ys3Lk0TSwHjGBOuBe5E8fGjS1xtRyvAYq5J8K3gV2CQKZW6K', 'inactive', 2);
