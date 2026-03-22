-- Argus Catalog Server - MariaDB/MySQL Schema
-- Database: argus_catalog

-- ---------------------------------------------------------------------------
-- Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_configuration (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL DEFAULT '',
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO catalog_configuration (category, config_key, config_value, description)
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
    ('cors', 'cors_origins', '*', 'Allowed CORS origins (comma-separated)');

-- ---------------------------------------------------------------------------
-- User Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS argus_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    role_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES argus_roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO argus_roles (role_id, name, description)
VALUES
    ('argus-admin', 'Admin', 'Administrator with full access'),
    ('argus-superuser', 'Superuser', 'Superuser with elevated access'),
    ('argus-user', 'User', 'Standard user with limited access');

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
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    role_id = VALUES(role_id);

-- ---------------------------------------------------------------------------
-- Catalog - Platforms
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platforms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(100) NOT NULL,
    logo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_platform_configurations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL UNIQUE,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Catalog - Platform Metadata
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_data_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    type_category VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_platform_data_type (platform_id, type_name),
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_platform_table_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_platform_table_type (platform_id, type_name),
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_platform_storage_formats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL,
    format_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_platform_storage_format (platform_id, format_name),
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_platform_features (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL,
    feature_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    value_type VARCHAR(50) NOT NULL,
    is_required VARCHAR(5) DEFAULT 'false',
    ordinal INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_platform_feature (platform_id, feature_key),
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Catalog - Datasets
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    urn VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    platform_id INT NOT NULL,
    description TEXT,
    origin VARCHAR(50) NOT NULL DEFAULT 'PROD',
    qualified_name VARCHAR(500),
    table_type VARCHAR(100),
    storage_format VARCHAR(100),
    platform_properties TEXT,
    is_synced VARCHAR(5) DEFAULT 'false',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_dataset_properties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    property_key VARCHAR(100) NOT NULL,
    property_value TEXT NOT NULL,
    UNIQUE KEY uq_dataset_property (dataset_id, property_key),
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_dataset_schemas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
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
    ordinal INT NOT NULL DEFAULT 0,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_schema_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_json TEXT NOT NULL,
    field_count INT DEFAULT 0,
    change_summary VARCHAR(500),
    changes_json TEXT,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Catalog - Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7) DEFAULT '#3b82f6',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_dataset_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    tag_id INT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES catalog_tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Catalog - Glossary
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_glossary_terms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    source VARCHAR(100),
    parent_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES catalog_glossary_terms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_dataset_glossary_terms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    term_id INT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (term_id) REFERENCES catalog_glossary_terms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Catalog - Owners
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_owners (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50) NOT NULL DEFAULT 'TECHNICAL_OWNER',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- ML Model Registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_registered_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    urn VARCHAR(500) NOT NULL UNIQUE,
    platform_id INT,
    description TEXT,
    owner VARCHAR(200),
    storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
    storage_location VARCHAR(1000),
    bucket_name VARCHAR(255),
    max_version_number INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    FOREIGN KEY (platform_id) REFERENCES catalog_platforms(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
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
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    UNIQUE KEY uq_model_version (model_id, version),
    FOREIGN KEY (model_id) REFERENCES catalog_registered_models(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_version_id INT NOT NULL,
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
    time_created TIMESTAMP NULL,
    requirements TEXT,
    conda TEXT,
    python_env TEXT,
    manifest TEXT,
    config TEXT,
    content_digest VARCHAR(100),
    source_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_catalog_model (model_name, version),
    FOREIGN KEY (model_version_id) REFERENCES catalog_model_versions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Collector - Hive Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_hive_query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hive_query_history_query_id (query_id),
    INDEX idx_hive_query_history_status (status),
    INDEX idx_hive_query_history_platform_id (platform_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Collector - Impala Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_impala_query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_type VARCHAR(32),
    query_state VARCHAR(32),
    statement TEXT,
    plan TEXT,
    `database` VARCHAR(256),
    username VARCHAR(256),
    connected_user VARCHAR(256),
    delegate_user VARCHAR(256),
    coordinator_host VARCHAR(512),
    start_time TIMESTAMP NULL,
    end_time TIMESTAMP NULL,
    duration_ms BIGINT,
    rows_produced BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_impala_query_history_query_id (query_id),
    INDEX idx_impala_query_history_platform_id (platform_id),
    INDEX idx_impala_query_history_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Collector - Trino Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_trino_query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_state VARCHAR(32),
    query_type VARCHAR(32),
    statement TEXT,
    plan TEXT,
    username VARCHAR(256),
    principal VARCHAR(256),
    source VARCHAR(256),
    catalog VARCHAR(256),
    `schema` VARCHAR(256),
    remote_client_address VARCHAR(256),
    create_time TIMESTAMP NULL,
    execution_start_time TIMESTAMP NULL,
    end_time TIMESTAMP NULL,
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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trino_query_history_query_id (query_id),
    INDEX idx_trino_query_history_platform_id (platform_id),
    INDEX idx_trino_query_history_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Collector - StarRocks Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_starrocks_query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    statement TEXT,
    digest VARCHAR(64),
    username VARCHAR(256),
    authorized_user VARCHAR(256),
    client_ip VARCHAR(64),
    `database` VARCHAR(256),
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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_starrocks_query_history_query_id (query_id),
    INDEX idx_starrocks_query_history_platform_id (platform_id),
    INDEX idx_starrocks_query_history_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Lineage - Query Lineage (per-query source→target table mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_query_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_hist_id INT,
    source_table VARCHAR(512) NOT NULL,
    target_table VARCHAR(512) NOT NULL,
    source_dataset_id INT,
    target_dataset_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_query_lineage_query_hist_id (query_hist_id),
    INDEX idx_query_lineage_source_table (source_table),
    INDEX idx_query_lineage_target_table (target_table),
    FOREIGN KEY (query_hist_id) REFERENCES argus_collector_hive_query_history(id) ON DELETE SET NULL,
    FOREIGN KEY (source_dataset_id) REFERENCES catalog_datasets(id) ON DELETE SET NULL,
    FOREIGN KEY (target_dataset_id) REFERENCES catalog_datasets(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Lineage - Column Lineage (per-query source→target column mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_column_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_lineage_id INT NOT NULL,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT',
    INDEX idx_column_lineage_query_lineage_id (query_lineage_id),
    FOREIGN KEY (query_lineage_id) REFERENCES argus_query_lineage(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Lineage - Data Pipeline (ETL/CDC/file-export pipeline registry)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_data_pipeline (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    pipeline_type VARCHAR(64) NOT NULL DEFAULT 'ETL',
    schedule VARCHAR(100),
    owner VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Lineage (aggregated dataset-to-dataset relationships)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_dataset_id INT NOT NULL,
    target_dataset_id INT NOT NULL,
    relation_type VARCHAR(32) NOT NULL DEFAULT 'READ_WRITE',
    lineage_source VARCHAR(32) NOT NULL DEFAULT 'QUERY_AGGREGATED',
    pipeline_id INT,
    description TEXT,
    created_by VARCHAR(200),
    query_count INT NOT NULL DEFAULT 0,
    last_query_id VARCHAR(256),
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_dataset_lineage (source_dataset_id, target_dataset_id, relation_type),
    INDEX idx_dataset_lineage_source (source_dataset_id),
    INDEX idx_dataset_lineage_target (target_dataset_id),
    INDEX idx_dataset_lineage_pipeline (pipeline_id),
    FOREIGN KEY (source_dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (target_dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (pipeline_id) REFERENCES argus_data_pipeline(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Column Mapping (cross-platform column-level lineage)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_column_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_lineage_id INT NOT NULL,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT',
    transform_expr VARCHAR(500),
    UNIQUE KEY uq_column_mapping (dataset_lineage_id, source_column, target_column),
    INDEX idx_dataset_column_mapping_lineage (dataset_lineage_id),
    FOREIGN KEY (dataset_lineage_id) REFERENCES argus_dataset_lineage(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Model Download Log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_model_download_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_model_download_log_name_at (model_name, downloaded_at),
    INDEX idx_model_download_log_at (downloaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    parent_id INT,
    root_id INT,
    depth INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    content_plain TEXT,
    category VARCHAR(20) NOT NULL DEFAULT 'general',
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(255),
    author_avatar VARCHAR(500),
    reply_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    INDEX idx_comments_entity (entity_type, entity_id, is_deleted),
    INDEX idx_comments_root (root_id),
    INDEX idx_comments_parent (parent_id),
    INDEX idx_comments_created (created_at),
    FOREIGN KEY (parent_id) REFERENCES catalog_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (root_id) REFERENCES catalog_comments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- OCI Model Hub
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_oci_model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    version INT NOT NULL,
    manifest TEXT,
    content_digest VARCHAR(100),
    file_count INT DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    metadata JSON,
    status VARCHAR(20) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_oci_model_version (model_id, version),
    FOREIGN KEY (model_id) REFERENCES catalog_oci_models(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_oci_model_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    tag_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_oci_model_tag (model_id, tag_id),
    FOREIGN KEY (model_id) REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES catalog_tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_oci_model_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    relation_type VARCHAR(30) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES catalog_oci_models(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_oci_model_download_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_oci_model_download_log_name_at (model_name, downloaded_at),
    INDEX idx_oci_model_download_log_at (downloaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
