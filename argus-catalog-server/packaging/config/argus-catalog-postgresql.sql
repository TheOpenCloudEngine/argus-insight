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

CREATE TABLE IF NOT EXISTS catalog_registered_models (
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

CREATE TABLE IF NOT EXISTS catalog_model_versions (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_registered_models(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS catalog_models (
    id SERIAL PRIMARY KEY,
    model_version_id INT NOT NULL REFERENCES catalog_model_versions(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    predict_fn VARCHAR(100),
    python_version VARCHAR(20),
    serialization_format VARCHAR(50),
    sklearn_version VARCHAR(20),
    mlflow_version VARCHAR(20),
    mlflow_model_id VARCHAR(100),
    model_size_bytes BIGINT,
    utc_time_created VARCHAR(50),
    time_created TIMESTAMPTZ,
    requirements TEXT,
    conda TEXT,
    python_env TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_name, version)
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
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_query_id
    ON argus_collector_hive_query_history (query_id);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_status
    ON argus_collector_hive_query_history (status);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_platform_id
    ON argus_collector_hive_query_history (platform_id);

-- ---------------------------------------------------------------------------
-- Collector - Impala Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_impala_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_type VARCHAR(32),
    query_state VARCHAR(32),
    statement TEXT,
    plan TEXT,
    database VARCHAR(256),
    username VARCHAR(256),
    connected_user VARCHAR(256),
    delegate_user VARCHAR(256),
    coordinator_host VARCHAR(512),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_ms BIGINT,
    rows_produced BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impala_query_history_query_id
    ON argus_collector_impala_query_history (query_id);

CREATE INDEX IF NOT EXISTS idx_impala_query_history_platform_id
    ON argus_collector_impala_query_history (platform_id);

CREATE INDEX IF NOT EXISTS idx_impala_query_history_username
    ON argus_collector_impala_query_history (username);

-- ---------------------------------------------------------------------------
-- Collector - Trino Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_trino_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_state VARCHAR(32),
    query_type VARCHAR(32),
    statement TEXT,
    plan TEXT,
    username VARCHAR(256),
    principal VARCHAR(256),
    source VARCHAR(256),
    catalog VARCHAR(256),
    schema VARCHAR(256),
    remote_client_address VARCHAR(256),
    create_time TIMESTAMPTZ,
    execution_start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    wall_time_ms BIGINT,
    cpu_time_ms BIGINT,
    physical_input_bytes BIGINT,
    physical_input_rows BIGINT,
    output_bytes BIGINT,
    output_rows BIGINT,
    peak_memory_bytes BIGINT,
    error_code VARCHAR(128),
    error_message TEXT,
    inputs_json TEXT,
    output_json TEXT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trino_query_history_query_id
    ON argus_collector_trino_query_history (query_id);

CREATE INDEX IF NOT EXISTS idx_trino_query_history_platform_id
    ON argus_collector_trino_query_history (platform_id);

CREATE INDEX IF NOT EXISTS idx_trino_query_history_username
    ON argus_collector_trino_query_history (username);

-- ---------------------------------------------------------------------------
-- Collector - StarRocks Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_starrocks_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    statement TEXT,
    digest VARCHAR(64),
    username VARCHAR(256),
    authorized_user VARCHAR(256),
    client_ip VARCHAR(64),
    database VARCHAR(256),
    catalog VARCHAR(256),
    state VARCHAR(16),
    error_code VARCHAR(512),
    query_time_ms BIGINT,
    scan_rows BIGINT,
    scan_bytes BIGINT,
    return_rows BIGINT,
    cpu_cost_ns BIGINT,
    mem_cost_bytes BIGINT,
    pending_time_ms BIGINT,
    is_query INT,
    fe_ip VARCHAR(128),
    event_timestamp BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_query_id
    ON argus_collector_starrocks_query_history (query_id);

CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_platform_id
    ON argus_collector_starrocks_query_history (platform_id);

CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_username
    ON argus_collector_starrocks_query_history (username);

-- ---------------------------------------------------------------------------
-- Lineage - Query Lineage (per-query source→target table mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_query_lineage (
    id SERIAL PRIMARY KEY,
    query_hist_id INTEGER REFERENCES argus_collector_hive_query_history(id) ON DELETE SET NULL,
    source_table VARCHAR(512) NOT NULL,
    target_table VARCHAR(512) NOT NULL,
    source_dataset_id INTEGER REFERENCES catalog_datasets(id) ON DELETE SET NULL,
    target_dataset_id INTEGER REFERENCES catalog_datasets(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_lineage_query_hist_id
    ON argus_query_lineage (query_hist_id);

CREATE INDEX IF NOT EXISTS idx_query_lineage_source_table
    ON argus_query_lineage (source_table);

CREATE INDEX IF NOT EXISTS idx_query_lineage_target_table
    ON argus_query_lineage (target_table);

-- ---------------------------------------------------------------------------
-- Lineage - Column Lineage (per-query source→target column mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_column_lineage (
    id SERIAL PRIMARY KEY,
    query_lineage_id INTEGER NOT NULL REFERENCES argus_query_lineage(id) ON DELETE CASCADE,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT'
);

CREATE INDEX IF NOT EXISTS idx_column_lineage_query_lineage_id
    ON argus_column_lineage (query_lineage_id);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Lineage (aggregated dataset-to-dataset relationships)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_lineage (
    id SERIAL PRIMARY KEY,
    source_dataset_id INTEGER NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    target_dataset_id INTEGER NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL DEFAULT 'READ_WRITE',
    query_count INTEGER NOT NULL DEFAULT 1,
    last_query_id VARCHAR(256),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_dataset_id, target_dataset_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_source
    ON argus_dataset_lineage (source_dataset_id);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_target
    ON argus_dataset_lineage (target_dataset_id);
