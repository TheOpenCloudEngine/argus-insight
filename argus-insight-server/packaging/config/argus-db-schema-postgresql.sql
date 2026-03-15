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

CREATE TABLE IF NOT EXISTS argus_agents (
    hostname        VARCHAR(255)    PRIMARY KEY,
    ip_address      VARCHAR(45)     NOT NULL,
    version         VARCHAR(50),
    kernel_version  VARCHAR(255),
    os_version      VARCHAR(255),
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
