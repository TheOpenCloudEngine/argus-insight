-- Argus Catalog Server - PostgreSQL Schema
-- Database: argus_catalog

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_configuration (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL DEFAULT '',
    description VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO catalog_configuration (category, config_key, config_value, description)
VALUES
    ('object_storage', 'object_storage_endpoint', 'http://localhost:9000', 'S3-compatible endpoint URL'),
    ('object_storage', 'object_storage_access_key', 'minioadmin', 'S3 access key'),
    ('object_storage', 'object_storage_secret_key', 'minioadmin', 'S3 secret key'),
    ('object_storage', 'object_storage_region', 'us-east-1', 'S3 region'),
    ('object_storage', 'object_storage_use_ssl', 'false', 'Use SSL for S3 connection'),
    ('object_storage', 'object_storage_bucket', 'model-artifacts', 'S3 bucket for model artifacts'),
    ('object_storage', 'object_storage_presigned_url_expiry', '3600', 'Presigned URL expiry in seconds'),
    ('auth', 'auth_type', 'keycloak', 'Authentication type'),
    ('auth', 'auth_keycloak_server_url', 'http://localhost:8180', 'Keycloak server URL'),
    ('auth', 'auth_keycloak_realm', 'argus', 'Keycloak realm'),
    ('auth', 'auth_keycloak_client_id', 'argus-client', 'Keycloak client ID'),
    ('auth', 'auth_keycloak_client_secret', 'argus-client-secret', 'Keycloak client secret'),
    ('auth', 'auth_keycloak_admin_role', 'argus-admin', 'Admin role name'),
    ('auth', 'auth_keycloak_superuser_role', 'argus-supseruser', 'Superuser role name'),
    ('auth', 'auth_keycloak_user_role', 'argus-user', 'User role name'),
    ('cors', 'cors_origins', '*', 'Allowed CORS origins (comma-separated)')
ON CONFLICT (config_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- User Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id SERIAL PRIMARY KEY,
    role_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
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

INSERT INTO argus_roles (role_id, name, description)
VALUES
    ('argus-admin', 'Admin', 'Administrator with full access'),
    ('argus-superuser', 'Superuser', 'Superuser with elevated access'),
    ('argus-user', 'User', 'Standard user with limited access')
ON CONFLICT (role_id) DO NOTHING;

INSERT INTO argus_users (username, email, first_name, last_name, password_hash, status, role_id)
VALUES (
    'admin',
    'admin@argus.local',
    'Admin',
    'User',
    '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
    'active',
    (SELECT id FROM argus_roles WHERE role_id = 'argus-admin')
)
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role_id = EXCLUDED.role_id;

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
    is_partition_key VARCHAR(5) DEFAULT 'false',
    is_distribution_key VARCHAR(5) DEFAULT 'false',
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
    storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
    storage_location VARCHAR(1000),
    bucket_name VARCHAR(255),
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
    manifest TEXT,
    config TEXT,
    content_digest VARCHAR(100),
    source_type VARCHAR(50),
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
-- Lineage - Data Pipeline (ETL/CDC/file-export pipeline registry)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_data_pipeline (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    pipeline_type VARCHAR(64) NOT NULL DEFAULT 'ETL',
    schedule VARCHAR(100),
    owner VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Lineage (aggregated dataset-to-dataset relationships)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_lineage (
    id SERIAL PRIMARY KEY,
    source_dataset_id INTEGER NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    target_dataset_id INTEGER NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL DEFAULT 'READ_WRITE',
    lineage_source VARCHAR(32) NOT NULL DEFAULT 'QUERY_AGGREGATED',
    pipeline_id INTEGER REFERENCES argus_data_pipeline(id) ON DELETE SET NULL,
    description TEXT,
    created_by VARCHAR(200),
    query_count INTEGER NOT NULL DEFAULT 0,
    last_query_id VARCHAR(256),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_dataset_id, target_dataset_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_source
    ON argus_dataset_lineage (source_dataset_id);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_target
    ON argus_dataset_lineage (target_dataset_id);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_pipeline
    ON argus_dataset_lineage (pipeline_id);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Column Mapping (cross-platform column-level lineage)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_column_mapping (
    id SERIAL PRIMARY KEY,
    dataset_lineage_id INTEGER NOT NULL REFERENCES argus_dataset_lineage(id) ON DELETE CASCADE,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT',
    transform_expr VARCHAR(500),
    UNIQUE (dataset_lineage_id, source_column, target_column)
);

CREATE INDEX IF NOT EXISTS idx_dataset_column_mapping_lineage
    ON argus_dataset_column_mapping (dataset_lineage_id);


-- ---------------------------------------------------------------------------
-- Model Download Log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_model_download_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_download_log_name_at
    ON catalog_model_download_log (model_name, downloaded_at);

CREATE INDEX IF NOT EXISTS idx_model_download_log_at
    ON catalog_model_download_log (downloaded_at);

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_comments (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    parent_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    root_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    depth INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    content_plain TEXT,
    category VARCHAR(20) NOT NULL DEFAULT 'general',
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(255),
    author_avatar VARCHAR(500),
    reply_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_comments_entity
    ON catalog_comments (entity_type, entity_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_comments_root
    ON catalog_comments (root_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent
    ON catalog_comments (parent_id);
CREATE INDEX IF NOT EXISTS idx_comments_created
    ON catalog_comments (created_at DESC);

-- ---------------------------------------------------------------------------
-- OCI Model Hub
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    description TEXT,
    readme TEXT,
    task VARCHAR(50),
    framework VARCHAR(50),
    language VARCHAR(50),
    license VARCHAR(100),
    source_type VARCHAR(50),
    source_id VARCHAR(500),
    source_revision VARCHAR(100),
    bucket VARCHAR(255),
    storage_prefix VARCHAR(500),
    owner VARCHAR(200),
    version_count INT NOT NULL DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    download_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_oci_model_versions (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    version INT NOT NULL,
    manifest TEXT,
    content_digest VARCHAR(100),
    file_count INT DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    metadata JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_id, version)
);

CREATE TABLE IF NOT EXISTS catalog_oci_model_tags (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_id, tag_id)
);

CREATE TABLE IF NOT EXISTS catalog_oci_model_lineage (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    relation_type VARCHAR(30) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_oci_model_download_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oci_model_download_log_name_at
    ON catalog_oci_model_download_log (model_name, downloaded_at);

CREATE INDEX IF NOT EXISTS idx_oci_model_download_log_at
    ON catalog_oci_model_download_log (downloaded_at);

-- ---------------------------------------------------------------------------
-- Semantic Search - Dataset Embeddings (pgvector)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_embeddings (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL UNIQUE REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    source_text TEXT NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    dimension INT NOT NULL DEFAULT 384,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_embeddings_ivfflat
    ON catalog_dataset_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ---------------------------------------------------------------------------
-- Alert - Subscription (who wants to be notified about what)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_subscription (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(200) NOT NULL,
    scope_type VARCHAR(32) NOT NULL,
    scope_id INTEGER,
    channels VARCHAR(200) NOT NULL DEFAULT 'IN_APP',
    severity_filter VARCHAR(16) NOT NULL DEFAULT 'WARNING',
    is_active VARCHAR(5) NOT NULL DEFAULT 'true',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_sub_user
    ON argus_alert_subscription (user_id);

CREATE INDEX IF NOT EXISTS idx_alert_sub_scope
    ON argus_alert_subscription (scope_type, scope_id);

-- ---------------------------------------------------------------------------
-- Alert - Lineage Alert (schema change impact events)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_lineage_alert (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    source_dataset_id INTEGER NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    affected_dataset_id INTEGER REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    lineage_id INTEGER REFERENCES argus_dataset_lineage(id) ON DELETE SET NULL,
    change_summary VARCHAR(500) NOT NULL,
    change_detail TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    resolved_by VARCHAR(200),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lineage_alert_source
    ON argus_lineage_alert (source_dataset_id);

CREATE INDEX IF NOT EXISTS idx_lineage_alert_affected
    ON argus_lineage_alert (affected_dataset_id);

CREATE INDEX IF NOT EXISTS idx_lineage_alert_status
    ON argus_lineage_alert (status);

-- ---------------------------------------------------------------------------
-- Alert - Notification Log (delivery records)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_notification (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER NOT NULL REFERENCES argus_lineage_alert(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    recipient VARCHAR(200) NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'SENT'
);

CREATE INDEX IF NOT EXISTS idx_alert_notification_alert
    ON argus_alert_notification (alert_id);
