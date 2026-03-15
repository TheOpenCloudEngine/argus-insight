-- Argus Insight Server - PostgreSQL Database and User Setup
-- Run this script as a PostgreSQL superuser (e.g., postgres)
--
-- Usage:
--   sudo -u postgres psql -f argus-db-schema-postgresql.sql

-- Create user
CREATE USER argus WITH PASSWORD 'argus';

-- Create database
CREATE DATABASE argus
    OWNER = argus
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE argus TO argus;

-- Connect to the argus database and set up schema permissions
\c argus

GRANT ALL PRIVILEGES ON SCHEMA public TO argus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO argus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO argus;
