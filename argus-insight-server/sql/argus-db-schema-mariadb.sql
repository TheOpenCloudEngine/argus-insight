-- Argus Insight Server - Database Schema (MariaDB / MySQL)
-- Run this script to create the required tables.

CREATE TABLE IF NOT EXISTS argus_agents (
    hostname        VARCHAR(255)    PRIMARY KEY,
    ip_address      VARCHAR(45)     NOT NULL,
    version         VARCHAR(50),
    kernel_version  VARCHAR(255),
    os_version      VARCHAR(255),
    cpu_usage       DOUBLE,
    memory_usage    DOUBLE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'UNREGISTERED',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS argus_agents_heartbeat (
    hostname            VARCHAR(255)    PRIMARY KEY,
    last_heartbeat_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
