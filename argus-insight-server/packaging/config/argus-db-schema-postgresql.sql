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
    name        VARCHAR(50)     NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE argus_roles IS 'Role master table defining available user roles';
COMMENT ON COLUMN argus_roles.id IS 'Auto-incremented role identifier';
COMMENT ON COLUMN argus_roles.name IS 'Unique role name (e.g. Admin, User)';
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
    password_hash   VARCHAR(255)    NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
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
COMMENT ON COLUMN argus_users.password_hash IS 'Bcrypt-hashed password';
COMMENT ON COLUMN argus_users.status IS 'Account status: active | inactive';
COMMENT ON COLUMN argus_users.role_id IS 'Foreign key to argus_roles(id)';
COMMENT ON COLUMN argus_users.created_at IS 'Account creation timestamp';
COMMENT ON COLUMN argus_users.updated_at IS 'Account last update timestamp';

-- Seed default roles
INSERT INTO argus_roles (name, description) VALUES ('Admin', 'Administrator with full access') ON CONFLICT (name) DO NOTHING;
INSERT INTO argus_roles (name, description) VALUES ('User', 'Standard user with limited access') ON CONFLICT (name) DO NOTHING;

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
