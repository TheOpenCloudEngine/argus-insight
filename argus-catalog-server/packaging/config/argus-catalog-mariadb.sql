-- Argus Catalog Server - MariaDB DDL
-- Auto-generated from database schema

-- ---------------------------------------------------------------------------
-- Platform Registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platforms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    logo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    platform_id VARCHAR(36) NOT NULL UNIQUE,
    type VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Platform Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_configurations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL UNIQUE REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Dataset
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    urn VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id),
    description TEXT,
    origin VARCHAR(50) NOT NULL,
    qualified_name VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    table_type VARCHAR(100),
    storage_format VARCHAR(100),
    platform_properties TEXT,
    is_synced VARCHAR(5) DEFAULT 'false'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Dataset Properties
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_properties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    property_key VARCHAR(100) NOT NULL,
    property_value TEXT NOT NULL,
    UNIQUE (dataset_id, property_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Dataset Schema
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_schemas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    field_path VARCHAR(500) NOT NULL,
    field_type VARCHAR(100) NOT NULL,
    native_type VARCHAR(100),
    description TEXT,
    nullable VARCHAR(5),
    ordinal INT NOT NULL,
    is_primary_key VARCHAR(5) DEFAULT 'false',
    is_indexed VARCHAR(5) DEFAULT 'false',
    is_unique VARCHAR(5) DEFAULT 'false',
    is_partition_key VARCHAR(5) DEFAULT 'false',
    is_distribution_key VARCHAR(5) DEFAULT 'false'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Schema Snapshots (change history)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_schema_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_json TEXT NOT NULL,
    field_count INT,
    change_summary VARCHAR(500),
    changes_json TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Dataset-Tag Mapping
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Glossary Terms
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_glossary_terms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    parent_id INT REFERENCES catalog_glossary_terms(id),
    term_type VARCHAR(20) NOT NULL DEFAULT 'TERM',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Dataset-Glossary Mapping
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_glossary_terms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    term_id INT NOT NULL REFERENCES catalog_glossary_terms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Ownership
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_owners (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Platform Metadata - Data Types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_data_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    type_category VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Platform Metadata - Table Types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_table_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Platform Metadata - Storage Formats
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_storage_formats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    format_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, format_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Platform Metadata - Features
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_features (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    value_type VARCHAR(50) NOT NULL,
    is_required VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, feature_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- User Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    role_id INT NOT NULL REFERENCES argus_roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Role Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role_id VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



-- ---------------------------------------------------------------------------
-- ML Model Registry - Registered Models
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_registered_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    urn VARCHAR(500) NOT NULL UNIQUE,
    platform_id INT REFERENCES catalog_platforms(id) ON DELETE SET NULL,
    description TEXT,
    owner VARCHAR(200),
    storage_location VARCHAR(1000),
    max_version_number INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
    bucket_name VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- ML Model Registry - Model Versions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    version INT NOT NULL,
    source VARCHAR(1000),
    run_id VARCHAR(255),
    run_link VARCHAR(1000),
    description TEXT,
    status VARCHAR(30) NOT NULL,
    status_message TEXT,
    storage_location VARCHAR(1000),
    artifact_count INT,
    artifact_size INT,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    UNIQUE (model_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- ML Model Registry - Model Metadata
-- ---------------------------------------------------------------------------

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
    time_created TIMESTAMP,
    requirements TEXT,
    conda TEXT,
    python_env TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manifest TEXT,
    config TEXT,
    content_digest VARCHAR(100),
    source_type VARCHAR(50),
    UNIQUE (model_name, version)
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
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS ix_catalog_model_download_log_downloaded_at ON catalog_model_download_log (downloaded_at);
CREATE INDEX IF NOT EXISTS ix_catalog_model_download_log_model_name ON catalog_model_download_log (model_name);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Models
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
    version_count INT NOT NULL,
    total_size BIGINT,
    download_count INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- OCI Model Hub - Versions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    version INT NOT NULL,
    manifest TEXT,
    content_digest VARCHAR(100),
    file_count INT,
    total_size BIGINT,
    metadata JSON,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (model_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- OCI Model Hub - Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (model_id, tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- OCI Model Hub - Lineage
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    relation_type VARCHAR(30) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- OCI Model Hub - Download Log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_download_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS ix_catalog_oci_model_download_log_downloaded_at ON catalog_oci_model_download_log (downloaded_at);
CREATE INDEX IF NOT EXISTS ix_catalog_oci_model_download_log_model_name ON catalog_oci_model_download_log (model_name);

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    parent_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    root_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    depth INT NOT NULL,
    content TEXT NOT NULL,
    content_plain TEXT,
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(255),
    author_avatar VARCHAR(500),
    reply_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted VARCHAR(5) NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'general'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS ix_catalog_comments_entity_id ON catalog_comments (entity_id);
CREATE INDEX IF NOT EXISTS ix_catalog_comments_entity_type ON catalog_comments (entity_type);

-- ---------------------------------------------------------------------------
-- Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_configuration (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_hive_query_history_query_id ON argus_collector_hive_query_history (query_id);
CREATE INDEX IF NOT EXISTS idx_hive_query_history_status ON argus_collector_hive_query_history (status);

-- ---------------------------------------------------------------------------
-- Collector - Impala Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_impala_query_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_type VARCHAR(32),
    query_state VARCHAR(32),
    statement TEXT,
    database VARCHAR(256),
    username VARCHAR(256),
    coordinator_host VARCHAR(512),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_ms BIGINT,
    rows_produced BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    schema VARCHAR(256),
    remote_client_address VARCHAR(256),
    create_time TIMESTAMP,
    execution_start_time TIMESTAMP,
    end_time TIMESTAMP,
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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_trino_query_history_platform_id ON argus_collector_trino_query_history (platform_id);
CREATE INDEX IF NOT EXISTS idx_trino_query_history_query_id ON argus_collector_trino_query_history (query_id);
CREATE INDEX IF NOT EXISTS idx_trino_query_history_username ON argus_collector_trino_query_history (username);

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
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_platform_id ON argus_collector_starrocks_query_history (platform_id);
CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_query_id ON argus_collector_starrocks_query_history (query_id);
CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_username ON argus_collector_starrocks_query_history (username);

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Lineage - Column Lineage (per-query source→target column mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_column_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_lineage_id INT NOT NULL,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Lineage - Data Pipeline (ETL/CDC/file-export pipeline registry)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_data_pipeline (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    pipeline_type VARCHAR(64) NOT NULL,
    schedule VARCHAR(100),
    owner VARCHAR(200),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- Lineage - Dataset Lineage (aggregated dataset-to-dataset relationships)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_lineage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    target_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL,
    lineage_source VARCHAR(32) NOT NULL,
    pipeline_id INT REFERENCES argus_data_pipeline(id) ON DELETE SET NULL,
    description TEXT,
    created_by VARCHAR(200),
    query_count INT NOT NULL,
    last_query_id VARCHAR(256),
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_dataset_id, target_dataset_id, relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_dataset_lineage_pipeline ON argus_dataset_lineage (pipeline_id);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_source ON argus_dataset_lineage (source_dataset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_target ON argus_dataset_lineage (target_dataset_id);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Column Mapping (cross-platform column-level lineage)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_column_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_lineage_id INT NOT NULL REFERENCES argus_dataset_lineage(id) ON DELETE CASCADE,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL,
    transform_expr VARCHAR(500),
    UNIQUE (dataset_lineage_id, source_column, target_column)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_dataset_column_mapping_lineage ON argus_dataset_column_mapping (dataset_lineage_id);

-- ---------------------------------------------------------------------------
-- Alert - Alert Rule (what to watch, when to trigger, who to notify)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_rule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    description TEXT,
    scope_type VARCHAR(32) NOT NULL,
    scope_id INT,
    trigger_type VARCHAR(64) NOT NULL,
    trigger_config TEXT DEFAULT '{}',
    severity_override VARCHAR(16),
    channels VARCHAR(200) NOT NULL DEFAULT 'IN_APP',
    notify_owners VARCHAR(5) NOT NULL DEFAULT 'true',
    webhook_url VARCHAR(500),
    subscribers VARCHAR(2000),
    is_active VARCHAR(5) NOT NULL DEFAULT 'true',
    created_by VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_alert_rule_scope (scope_type, scope_id),
    INDEX idx_alert_rule_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Alert - Lineage Alert (schema change impact events)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_lineage_alert (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    source_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    affected_dataset_id INT REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    lineage_id INT REFERENCES argus_dataset_lineage(id) ON DELETE SET NULL,
    rule_id INT REFERENCES argus_alert_rule(id) ON DELETE SET NULL,
    change_summary VARCHAR(500) NOT NULL,
    change_detail TEXT,
    status VARCHAR(20) NOT NULL,
    resolved_by VARCHAR(200),
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lineage_alert_affected (affected_dataset_id),
    INDEX idx_lineage_alert_source (source_dataset_id),
    INDEX idx_lineage_alert_status (status),
    INDEX idx_lineage_alert_rule (rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Alert - Notification Log (delivery records)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_notification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_id INT NOT NULL REFERENCES argus_lineage_alert(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    recipient VARCHAR(200) NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE INDEX IF NOT EXISTS idx_alert_notification_alert ON argus_alert_notification (alert_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Dictionary (표준 사전)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_dictionary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dict_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    effective_date DATE,
    expiry_date DATE,
    created_by VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Word (표준 단어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_word (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dictionary_id INT NOT NULL,
    word_name VARCHAR(100) NOT NULL,
    word_english VARCHAR(100) NOT NULL,
    word_abbr VARCHAR(50) NOT NULL,
    description TEXT,
    word_type VARCHAR(20) NOT NULL DEFAULT 'GENERAL',
    is_forbidden VARCHAR(5) DEFAULT 'false',
    synonym_group_id INT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_std_word (dictionary_id, word_name),
    INDEX idx_std_word_dict (dictionary_id),
    INDEX idx_std_word_type (word_type),
    FOREIGN KEY (dictionary_id) REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Code Group (코드 그룹)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_code_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dictionary_id INT NOT NULL,
    group_name VARCHAR(200) NOT NULL,
    group_english VARCHAR(200),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_code_group (dictionary_id, group_name),
    FOREIGN KEY (dictionary_id) REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Code Value (코드 값)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_code_value (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code_group_id INT NOT NULL,
    code_value VARCHAR(100) NOT NULL,
    code_name VARCHAR(200) NOT NULL,
    code_english VARCHAR(200),
    description TEXT,
    sort_order INT NOT NULL DEFAULT 0,
    is_active VARCHAR(5) DEFAULT 'true',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_code_value (code_group_id, code_value),
    INDEX idx_code_value_group (code_group_id),
    FOREIGN KEY (code_group_id) REFERENCES catalog_code_group(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Domain (표준 도메인)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_domain (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dictionary_id INT NOT NULL,
    domain_name VARCHAR(100) NOT NULL,
    domain_group VARCHAR(100),
    data_type VARCHAR(50) NOT NULL,
    data_length INT,
    data_precision INT,
    data_scale INT,
    description TEXT,
    code_group_id INT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_std_domain (dictionary_id, domain_name),
    INDEX idx_std_domain_dict (dictionary_id),
    FOREIGN KEY (dictionary_id) REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    FOREIGN KEY (code_group_id) REFERENCES catalog_code_group(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Term (표준 용어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_term (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dictionary_id INT NOT NULL,
    term_name VARCHAR(200) NOT NULL,
    term_english VARCHAR(200) NOT NULL,
    term_abbr VARCHAR(100) NOT NULL,
    physical_name VARCHAR(100) NOT NULL,
    domain_id INT,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_std_term (dictionary_id, term_name),
    INDEX idx_std_term_dict (dictionary_id),
    INDEX idx_std_term_physical (physical_name),
    FOREIGN KEY (dictionary_id) REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES catalog_standard_domain(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Term Words (용어 구성 단어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_term_words (
    id INT AUTO_INCREMENT PRIMARY KEY,
    term_id INT NOT NULL,
    word_id INT NOT NULL,
    ordinal INT NOT NULL,
    UNIQUE KEY uq_term_words (term_id, word_id, ordinal),
    INDEX idx_std_term_words_term (term_id),
    FOREIGN KEY (term_id) REFERENCES catalog_standard_term(id) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES catalog_standard_word(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Term-Column Mapping (표준 용어 ↔ 실제 컬럼 매핑)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_term_column_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    term_id INT NOT NULL,
    dataset_id INT NOT NULL,
    schema_id INT NOT NULL,
    mapping_type VARCHAR(20) NOT NULL DEFAULT 'MATCHED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_term_col (term_id, schema_id),
    INDEX idx_term_col_mapping_term (term_id),
    INDEX idx_term_col_mapping_dataset (dataset_id),
    FOREIGN KEY (term_id) REFERENCES catalog_standard_term(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (schema_id) REFERENCES catalog_dataset_schemas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Standard - Change Log (변경 이력)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_change_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,
    entity_id INT NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(200),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_std_change_log_entity (entity_type, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Quality - Profile
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_data_profile (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    row_count BIGINT NOT NULL DEFAULT 0,
    profile_json TEXT NOT NULL,
    profiled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_data_profile_dataset (dataset_id),
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Quality - Rule
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_quality_rule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    column_name VARCHAR(256),
    expected_value TEXT,
    threshold DECIMAL(5,2) DEFAULT 100.00,
    severity VARCHAR(16) NOT NULL DEFAULT 'WARNING',
    is_active VARCHAR(5) NOT NULL DEFAULT 'true',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_quality_rule_dataset (dataset_id),
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Quality - Result
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_quality_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rule_id INT NOT NULL,
    dataset_id INT NOT NULL,
    passed VARCHAR(5) NOT NULL,
    actual_value TEXT,
    detail TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_quality_result_rule (rule_id),
    INDEX idx_quality_result_dataset (dataset_id),
    FOREIGN KEY (rule_id) REFERENCES catalog_quality_rule(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Data Quality - Score
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_quality_score (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    score DECIMAL(5,2) NOT NULL DEFAULT 0,
    total_rules INT NOT NULL DEFAULT 0,
    passed_rules INT NOT NULL DEFAULT 0,
    warning_rules INT NOT NULL DEFAULT 0,
    failed_rules INT NOT NULL DEFAULT 0,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_quality_score_dataset (dataset_id),
    FOREIGN KEY (dataset_id) REFERENCES catalog_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Seed: Source Analysis Platforms (Java / Python)
-- ---------------------------------------------------------------------------

INSERT IGNORE INTO catalog_platforms (name, logo_url, platform_id, type)
VALUES ('java', NULL, UUID(), 'source_analysis');

INSERT IGNORE INTO catalog_platforms (name, logo_url, platform_id, type)
VALUES ('python', NULL, UUID(), 'source_analysis');

-- ---------------------------------------------------------------------------
-- AI Metadata Generation
-- ---------------------------------------------------------------------------

-- Add PII type column to dataset schemas (idempotent via procedure)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'catalog_dataset_schemas' AND COLUMN_NAME = 'pii_type');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE catalog_dataset_schemas ADD COLUMN pii_type VARCHAR(50)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- AI generation log for audit, preview/apply workflow, and cost tracking
CREATE TABLE IF NOT EXISTS catalog_ai_generation_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,
    entity_id INT NOT NULL,
    dataset_id INT NOT NULL,
    field_name VARCHAR(500),
    generation_type VARCHAR(30) NOT NULL,
    generated_text TEXT NOT NULL,
    applied TINYINT(1) DEFAULT 0,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_tokens INT,
    completion_tokens INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_gen_log_dataset FOREIGN KEY (dataset_id)
        REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    INDEX idx_ai_gen_log_dataset (dataset_id),
    INDEX idx_ai_gen_log_applied (applied)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------

