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
    name        VARCHAR(50)     NOT NULL UNIQUE           COMMENT 'Unique role name (e.g. Admin, User)',
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
    password_hash   VARCHAR(255)    NOT NULL                  COMMENT 'Bcrypt-hashed password',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active' COMMENT 'Account status: active | inactive',
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
('domain', 'pdns_server_id', '', 'PowerDNS server ID'),
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
('command', 'openssl_path',      '/usr/bin/openssl',     'Path to OpenSSL binary');

-- ---------------------------------------------------------------------------
-- Notes tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_notebooks (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented notebook identifier',
    user_id         INT             NOT NULL                  COMMENT 'Owner user (FK to argus_users)',
    title           VARCHAR(255)    NOT NULL                  COMMENT 'Notebook display title',
    description     VARCHAR(500)                              COMMENT 'Optional notebook description',
    color           VARCHAR(20)     NOT NULL DEFAULT 'default' COMMENT 'Theme color identifier',
    is_pinned       BOOLEAN         NOT NULL DEFAULT FALSE    COMMENT 'Whether the notebook is pinned to top',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp',
    CONSTRAINT fk_notebook_user FOREIGN KEY (user_id) REFERENCES argus_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='User notebooks (top-level container for notes)';

CREATE TABLE IF NOT EXISTS argus_notebook_sections (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented section identifier',
    notebook_id     INT             NOT NULL                  COMMENT 'Parent notebook (FK to argus_notebooks)',
    title           VARCHAR(255)    NOT NULL                  COMMENT 'Section display title',
    color           VARCHAR(20)     NOT NULL DEFAULT 'default' COMMENT 'Theme color identifier',
    display_order   INT             NOT NULL DEFAULT 0        COMMENT 'Sort order within the notebook',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp',
    CONSTRAINT fk_section_notebook FOREIGN KEY (notebook_id) REFERENCES argus_notebooks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Sections within a notebook (tab-like grouping)';

CREATE TABLE IF NOT EXISTS argus_notebook_pages (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented page identifier',
    section_id      INT             NOT NULL                  COMMENT 'Parent section (FK to argus_notebook_sections)',
    title           VARCHAR(255)    NOT NULL                  COMMENT 'Page display title',
    content         LONGTEXT        NOT NULL                  COMMENT 'Markdown content of the page',
    display_order   INT             NOT NULL DEFAULT 0        COMMENT 'Sort order within the section',
    is_pinned       BOOLEAN         NOT NULL DEFAULT FALSE    COMMENT 'Whether the page is pinned to top',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record last update timestamp',
    CONSTRAINT fk_page_section FOREIGN KEY (section_id) REFERENCES argus_notebook_sections(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Pages within a section containing markdown content';

CREATE TABLE IF NOT EXISTS argus_notebook_page_versions (
    id              INT             AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incremented version identifier',
    page_id         INT             NOT NULL                  COMMENT 'Page this version belongs to',
    version         INT             NOT NULL                  COMMENT 'Incrementing version number per page',
    title           VARCHAR(255)    NOT NULL                  COMMENT 'Page title at this version',
    content         LONGTEXT        NOT NULL                  COMMENT 'Full markdown content snapshot',
    change_summary  VARCHAR(255)                              COMMENT 'Optional description of what changed',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    UNIQUE KEY uq_page_version (page_id, version),
    CONSTRAINT fk_version_page FOREIGN KEY (page_id) REFERENCES argus_notebook_pages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Version history snapshots for notebook pages';

-- Seed default roles
INSERT IGNORE INTO argus_roles (name, description) VALUES ('Admin', 'Administrator with full access');
INSERT IGNORE INTO argus_roles (name, description) VALUES ('User', 'Standard user with limited access');

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
