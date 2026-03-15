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
