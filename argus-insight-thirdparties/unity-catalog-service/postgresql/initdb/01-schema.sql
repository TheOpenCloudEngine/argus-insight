-- Unity Catalog PostgreSQL initialization
-- Tables are auto-created by Hibernate (hbm2ddl.auto=update)

-- Ensure the unity_catalog database and user have proper permissions
GRANT ALL PRIVILEGES ON DATABASE unity_catalog TO unity_catalog;
GRANT ALL PRIVILEGES ON SCHEMA public TO unity_catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO unity_catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO unity_catalog;
