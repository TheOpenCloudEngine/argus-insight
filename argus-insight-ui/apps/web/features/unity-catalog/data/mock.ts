import type {
  Catalog,
  Schema,
  UCTable,
  Volume,
  UCFunction,
  Model,
  ModelVersion,
} from "./schema"

const now = Date.now()
const hour = 3600000

export const mockCatalogs: Catalog[] = [
  { id: "cat-001", name: "unity", comment: "Default Unity Catalog", created_at: now - 72 * hour, updated_at: now - 2 * hour },
  { id: "cat-002", name: "production", comment: "Production data catalog", created_at: now - 48 * hour, updated_at: now - 1 * hour },
  { id: "cat-003", name: "staging", comment: "Staging environment catalog", created_at: now - 24 * hour, updated_at: now - hour },
]

export const mockSchemas: Schema[] = [
  { catalog_name: "unity", name: "default", full_name: "unity.default", comment: "Default schema", created_at: now - 70 * hour, updated_at: now - 3 * hour },
  { catalog_name: "unity", name: "ml_data", full_name: "unity.ml_data", comment: "Machine learning datasets", created_at: now - 60 * hour, updated_at: now - 2 * hour },
  { catalog_name: "production", name: "analytics", full_name: "production.analytics", comment: "Analytics data", created_at: now - 40 * hour, updated_at: now - hour },
  { catalog_name: "production", name: "raw", full_name: "production.raw", comment: "Raw ingested data", created_at: now - 38 * hour, updated_at: now - hour },
  { catalog_name: "staging", name: "test", full_name: "staging.test", comment: "Test schema", created_at: now - 20 * hour, updated_at: now - hour },
]

export const mockTables: UCTable[] = [
  { catalog_name: "unity", schema_name: "default", name: "users", table_id: "tbl-001", table_type: "MANAGED", data_source_format: "DELTA", storage_location: "s3://unity/default/users", comment: "User information table", columns: [{ name: "id", type_name: "LONG", position: 0 }, { name: "name", type_name: "STRING", position: 1 }, { name: "email", type_name: "STRING", position: 2 }, { name: "created_at", type_name: "TIMESTAMP", position: 3 }], created_at: now - 65 * hour, updated_at: now - 4 * hour },
  { catalog_name: "unity", schema_name: "default", name: "orders", table_id: "tbl-002", table_type: "MANAGED", data_source_format: "DELTA", storage_location: "s3://unity/default/orders", comment: "Order transactions", columns: [{ name: "order_id", type_name: "LONG", position: 0 }, { name: "user_id", type_name: "LONG", position: 1 }, { name: "amount", type_name: "DOUBLE", position: 2 }, { name: "status", type_name: "STRING", position: 3 }], created_at: now - 64 * hour, updated_at: now - 3 * hour },
  { catalog_name: "unity", schema_name: "default", name: "products", table_id: "tbl-003", table_type: "EXTERNAL", data_source_format: "PARQUET", storage_location: "s3://unity/default/products", comment: "Product catalog", columns: [{ name: "product_id", type_name: "LONG", position: 0 }, { name: "name", type_name: "STRING", position: 1 }, { name: "price", type_name: "DOUBLE", position: 2 }], created_at: now - 63 * hour, updated_at: now - 2 * hour },
  { catalog_name: "unity", schema_name: "ml_data", name: "training_features", table_id: "tbl-004", table_type: "MANAGED", data_source_format: "DELTA", storage_location: "s3://unity/ml_data/features", comment: "ML training features", columns: [{ name: "feature_id", type_name: "LONG", position: 0 }, { name: "vector", type_name: "ARRAY<DOUBLE>", position: 1 }, { name: "label", type_name: "STRING", position: 2 }], created_at: now - 55 * hour, updated_at: now - hour },
  { catalog_name: "production", schema_name: "analytics", name: "page_views", table_id: "tbl-005", table_type: "MANAGED", data_source_format: "DELTA", storage_location: "s3://prod/analytics/page_views", comment: "Website page views", columns: [{ name: "view_id", type_name: "LONG", position: 0 }, { name: "url", type_name: "STRING", position: 1 }, { name: "timestamp", type_name: "TIMESTAMP", position: 2 }], created_at: now - 35 * hour, updated_at: now - hour },
]

export const mockVolumes: Volume[] = [
  { catalog_name: "unity", schema_name: "default", name: "raw_files", volume_id: "vol-001", volume_type: "MANAGED", storage_location: "s3://unity/default/volumes/raw_files", full_name: "unity.default.raw_files", comment: "Raw file uploads", created_at: now - 60 * hour, updated_at: now - 5 * hour },
  { catalog_name: "unity", schema_name: "ml_data", name: "model_artifacts", volume_id: "vol-002", volume_type: "EXTERNAL", storage_location: "s3://ml-artifacts/", full_name: "unity.ml_data.model_artifacts", comment: "Trained model artifacts", created_at: now - 50 * hour, updated_at: now - 2 * hour },
  { catalog_name: "production", schema_name: "raw", name: "csv_imports", volume_id: "vol-003", volume_type: "MANAGED", storage_location: "s3://prod/raw/csv_imports", full_name: "production.raw.csv_imports", comment: "CSV data imports", created_at: now - 30 * hour, updated_at: now - hour },
]

export const mockFunctions: UCFunction[] = [
  { catalog_name: "unity", schema_name: "default", name: "calculate_total", function_id: "fn-001", input_params: { parameters: [{ name: "price", type_name: "DOUBLE", position: 0 }, { name: "quantity", type_name: "INT", position: 1 }, { name: "tax_rate", type_name: "DOUBLE", position: 2 }] }, data_type: "DOUBLE", routine_definition: "SELECT price * quantity * (1 + tax_rate)", external_language: "SQL", comment: "Calculate total with tax", created_at: now - 50 * hour, updated_at: now - 3 * hour },
  { catalog_name: "unity", schema_name: "default", name: "normalize_email", function_id: "fn-002", input_params: { parameters: [{ name: "email", type_name: "STRING", position: 0 }] }, data_type: "STRING", routine_definition: "SELECT LOWER(TRIM(email))", external_language: "SQL", comment: "Normalize email address", created_at: now - 48 * hour, updated_at: now - 2 * hour },
  { catalog_name: "unity", schema_name: "ml_data", name: "feature_transform", function_id: "fn-003", input_params: { parameters: [{ name: "input_vector", type_name: "ARRAY<DOUBLE>", position: 0 }] }, data_type: "ARRAY<DOUBLE>", routine_definition: "import numpy as np\ndef transform(v):\n  return (np.array(v) - np.mean(v)) / np.std(v)", external_language: "PYTHON", comment: "Standardize feature vector", created_at: now - 45 * hour, updated_at: now - hour },
]

export const mockModels: Model[] = [
  { catalog_name: "unity", schema_name: "ml_data", name: "fraud_detector", model_id: "mdl-001", comment: "Fraud detection model", created_at: now - 40 * hour, updated_at: now - 2 * hour },
  { catalog_name: "unity", schema_name: "ml_data", name: "recommendation_engine", model_id: "mdl-002", comment: "Product recommendation model", created_at: now - 35 * hour, updated_at: now - hour },
]

export const mockModelVersions: ModelVersion[] = [
  { catalog_name: "unity", schema_name: "ml_data", model_name: "fraud_detector", version: 1, source: "s3://ml-artifacts/fraud_detector/v1", run_id: "run-001", status: "READY", comment: "Initial version", created_at: now - 38 * hour, updated_at: now - 10 * hour },
  { catalog_name: "unity", schema_name: "ml_data", model_name: "fraud_detector", version: 2, source: "s3://ml-artifacts/fraud_detector/v2", run_id: "run-005", status: "READY", comment: "Improved accuracy", created_at: now - 20 * hour, updated_at: now - 2 * hour },
  { catalog_name: "unity", schema_name: "ml_data", model_name: "fraud_detector", version: 3, source: "s3://ml-artifacts/fraud_detector/v3", run_id: "run-010", status: "PENDING_REGISTRATION", comment: "Experimental", created_at: now - 5 * hour, updated_at: now - hour },
  { catalog_name: "unity", schema_name: "ml_data", model_name: "recommendation_engine", version: 1, source: "s3://ml-artifacts/recommender/v1", run_id: "run-003", status: "READY", comment: "Collaborative filtering v1", created_at: now - 30 * hour, updated_at: now - 5 * hour },
]
