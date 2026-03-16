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

-- Seed default roles
INSERT IGNORE INTO argus_roles (name, description) VALUES ('Admin', 'Administrator with full access');
INSERT IGNORE INTO argus_roles (name, description) VALUES ('User', 'Standard user with limited access');
