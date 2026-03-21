-- Argus Catalog Server - PostgreSQL Schema
-- Database: argus_catalog

-- ---------------------------------------------------------------------------
-- User Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS argus_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    role_id INT NOT NULL REFERENCES argus_roles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Catalog - Platforms
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platforms (
    id SERIAL PRIMARY KEY,
    platform_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(100) NOT NULL,
    logo_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_platform_configurations (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL UNIQUE REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Catalog - Platform Metadata
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_data_types (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    type_category VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE (platform_id, type_name)
);

CREATE TABLE IF NOT EXISTS catalog_platform_table_types (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE (platform_id, type_name)
);

CREATE TABLE IF NOT EXISTS catalog_platform_storage_formats (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    format_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE (platform_id, format_name)
);

CREATE TABLE IF NOT EXISTS catalog_platform_features (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    value_type VARCHAR(50) NOT NULL,
    is_required VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE (platform_id, feature_key)
);

-- ---------------------------------------------------------------------------
-- Catalog - Datasets
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_datasets (
    id SERIAL PRIMARY KEY,
    urn VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id),
    description TEXT,
    origin VARCHAR(50) NOT NULL DEFAULT 'PROD',
    qualified_name VARCHAR(500),
    table_type VARCHAR(100),
    storage_format VARCHAR(100),
    platform_properties TEXT,
    is_synced VARCHAR(5) DEFAULT 'false',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_dataset_properties (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    property_key VARCHAR(100) NOT NULL,
    property_value TEXT NOT NULL,
    UNIQUE (dataset_id, property_key)
);

CREATE TABLE IF NOT EXISTS catalog_dataset_schemas (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    field_path VARCHAR(500) NOT NULL,
    field_type VARCHAR(100) NOT NULL,
    native_type VARCHAR(100),
    description TEXT,
    nullable VARCHAR(5) DEFAULT 'true',
    is_primary_key VARCHAR(5) DEFAULT 'false',
    is_unique VARCHAR(5) DEFAULT 'false',
    is_indexed VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS catalog_schema_snapshots (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    schema_json TEXT NOT NULL,
    field_count INT DEFAULT 0,
    change_summary VARCHAR(500),
    changes_json TEXT
);

-- ---------------------------------------------------------------------------
-- Catalog - Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7) DEFAULT '#3b82f6',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_dataset_tags (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Catalog - Glossary
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_glossary_terms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    source VARCHAR(100),
    parent_id INT REFERENCES catalog_glossary_terms(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_dataset_glossary_terms (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    term_id INT NOT NULL REFERENCES catalog_glossary_terms(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Catalog - Owners
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_owners (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50) NOT NULL DEFAULT 'TECHNICAL_OWNER',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- ML Model Registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS models_registered_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    urn VARCHAR(500) NOT NULL UNIQUE,
    platform_id INT REFERENCES catalog_platforms(id) ON DELETE SET NULL,
    description TEXT,
    owner VARCHAR(200),
    storage_location VARCHAR(1000),
    max_version_number INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(200),
    updated_by VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS models_model_versions (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES models_registered_models(id) ON DELETE CASCADE,
    version INT NOT NULL,
    source VARCHAR(1000),
    run_id VARCHAR(255),
    run_link VARCHAR(1000),
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_REGISTRATION',
    status_message TEXT,
    storage_location VARCHAR(1000),
    artifact_count INT DEFAULT 0,
    artifact_size INT DEFAULT 0,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    UNIQUE (model_id, version)
);

-- ---------------------------------------------------------------------------
-- Collector - Hive Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_hive_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL,
    short_username VARCHAR(128),
    username VARCHAR(256),
    operation_name VARCHAR(64),
    start_time BIGINT,
    end_time BIGINT,
    duration_ms BIGINT,
    query TEXT,
    status VARCHAR(16) NOT NULL,
    error_msg TEXT,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_query_id
    ON argus_collector_hive_query_history (query_id);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_status
    ON argus_collector_hive_query_history (status);
