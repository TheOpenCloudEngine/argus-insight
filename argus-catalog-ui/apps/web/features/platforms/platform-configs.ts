export type PlatformFieldDef = {
  key: string
  label: string
  type: 'text' | 'number' | 'password' | 'select' | 'toggle'
  placeholder?: string
  required?: boolean
  defaultValue?: string | number | boolean
  options?: { label: string; value: string }[]
  showWhen?: { field: string; value: string }
}

// ---------------------------------------------------------------------------
// Shared field fragments
// ---------------------------------------------------------------------------

const hostField = (defaultPort: number): PlatformFieldDef[] => [
  { key: 'host', label: 'Host', type: 'text', required: true },
  { key: 'port', label: 'Port', type: 'number', required: true, defaultValue: defaultPort },
]

const dbCredentials: PlatformFieldDef[] = [
  { key: 'database', label: 'Database', type: 'text', required: true },
  { key: 'username', label: 'Username', type: 'text', required: true },
  { key: 'password', label: 'Password', type: 'password', required: true },
]

const sslToggle = (defaultValue = false): PlatformFieldDef => ({
  key: 'ssl_enabled',
  label: 'SSL Enabled',
  type: 'toggle',
  defaultValue,
})

const kerberosFields: PlatformFieldDef[] = [
  { key: 'kerberos_principal', label: 'Kerberos Principal', type: 'text', showWhen: { field: 'auth_type', value: 'KERBEROS' } },
  { key: 'kerberos_keytab', label: 'Kerberos Keytab', type: 'text', placeholder: '/path/to/keytab', showWhen: { field: 'auth_type', value: 'KERBEROS' } },
]

const ldapFields: PlatformFieldDef[] = [
  { key: 'ldap_username', label: 'LDAP Username', type: 'text', showWhen: { field: 'auth_type', value: 'LDAP' } },
  { key: 'ldap_password', label: 'LDAP Password', type: 'password', showWhen: { field: 'auth_type', value: 'LDAP' } },
]

const hadoopAuthType = (options: string[]): PlatformFieldDef => ({
  key: 'auth_type',
  label: 'Authentication',
  type: 'select',
  required: true,
  defaultValue: 'NONE',
  options: options.map((v) => ({ label: v, value: v })),
})

// ---------------------------------------------------------------------------
// Helpers for RDBMS-like platforms
// ---------------------------------------------------------------------------

function rdbmsConfig(defaultPort: number): PlatformFieldDef[] {
  return [...hostField(defaultPort), ...dbCredentials, sslToggle()]
}

// ---------------------------------------------------------------------------
// Platform configurations
// ---------------------------------------------------------------------------

export const PLATFORM_CONFIGS: Record<string, PlatformFieldDef[]> = {
  // ---- RDBMS-like --------------------------------------------------------
  postgresql: rdbmsConfig(5432),
  mysql: rdbmsConfig(3306),
  greenplum: rdbmsConfig(5432),
  redshift: rdbmsConfig(5439),
  starrocks: rdbmsConfig(9030),

  // ---- Snowflake ---------------------------------------------------------
  snowflake: [
    { key: 'account', label: 'Account', type: 'text', required: true, placeholder: 'org-account' },
    { key: 'warehouse', label: 'Warehouse', type: 'text' },
    { key: 'database', label: 'Database', type: 'text', required: true },
    { key: 'schema', label: 'Schema', type: 'text', defaultValue: 'PUBLIC' },
    { key: 'username', label: 'Username', type: 'text', required: true },
    { key: 'password', label: 'Password', type: 'password', required: true },
    { key: 'role', label: 'Role', type: 'text' },
  ],

  // ---- BigQuery ----------------------------------------------------------
  bigquery: [
    { key: 'project_id', label: 'Project ID', type: 'text', required: true },
    { key: 'dataset', label: 'Dataset', type: 'text' },
    { key: 'credentials_json', label: 'Credentials JSON', type: 'text', placeholder: 'Paste service account JSON' },
  ],

  // ---- Hive --------------------------------------------------------------
  hive: [
    { key: 'metastore_host', label: 'Metastore Host', type: 'text', required: true },
    { key: 'metastore_port', label: 'Metastore Port', type: 'number', required: true, defaultValue: 9083 },
    hadoopAuthType(['NONE', 'LDAP', 'KERBEROS']),
    ...ldapFields,
    ...kerberosFields,
  ],

  // ---- Impala ------------------------------------------------------------
  impala: [
    ...hostField(21050),
    hadoopAuthType(['NONE', 'LDAP', 'KERBEROS']),
    ...ldapFields,
    ...kerberosFields,
    { key: 'use_ssl', label: 'Use SSL', type: 'toggle', defaultValue: false },
  ],

  // ---- Trino -------------------------------------------------------------
  trino: [
    ...hostField(8443),
    { key: 'catalog', label: 'Catalog', type: 'text', required: true },
    { key: 'schema', label: 'Schema', type: 'text' },
    { key: 'username', label: 'Username', type: 'text', required: true },
    { key: 'password', label: 'Password', type: 'password' },
    { key: 'use_ssl', label: 'Use SSL', type: 'toggle', defaultValue: true },
  ],

  // ---- Kafka -------------------------------------------------------------
  kafka: [
    { key: 'bootstrap_servers', label: 'Bootstrap Servers', type: 'text', required: true, placeholder: 'host1:9092,host2:9092' },
    {
      key: 'security_protocol',
      label: 'Security Protocol',
      type: 'select',
      defaultValue: 'PLAINTEXT',
      options: [
        { label: 'PLAINTEXT', value: 'PLAINTEXT' },
        { label: 'SSL', value: 'SSL' },
        { label: 'SASL_PLAINTEXT', value: 'SASL_PLAINTEXT' },
        { label: 'SASL_SSL', value: 'SASL_SSL' },
      ],
    },
    { key: 'sasl_mechanism', label: 'SASL Mechanism', type: 'text', showWhen: { field: 'security_protocol', value: 'SASL_PLAINTEXT' } },
    { key: 'sasl_username', label: 'SASL Username', type: 'text', showWhen: { field: 'security_protocol', value: 'SASL_PLAINTEXT' } },
    { key: 'sasl_password', label: 'SASL Password', type: 'password', showWhen: { field: 'security_protocol', value: 'SASL_PLAINTEXT' } },
    // Duplicate entries for SASL_SSL so the fields also appear for that protocol
    { key: 'sasl_mechanism', label: 'SASL Mechanism', type: 'text', showWhen: { field: 'security_protocol', value: 'SASL_SSL' } },
    { key: 'sasl_username', label: 'SASL Username', type: 'text', showWhen: { field: 'security_protocol', value: 'SASL_SSL' } },
    { key: 'sasl_password', label: 'SASL Password', type: 'password', showWhen: { field: 'security_protocol', value: 'SASL_SSL' } },
    { key: 'schema_registry_url', label: 'Schema Registry URL', type: 'text', placeholder: 'http://schema-registry:8081' },
  ],

  // ---- Elasticsearch -----------------------------------------------------
  elasticsearch: [
    { key: 'hosts', label: 'Hosts', type: 'text', required: true, placeholder: 'http://localhost:9200' },
    { key: 'username', label: 'Username', type: 'text' },
    { key: 'password', label: 'Password', type: 'password' },
    { key: 'use_ssl', label: 'Use SSL', type: 'toggle', defaultValue: false },
    { key: 'ca_cert_path', label: 'CA Certificate Path', type: 'text', placeholder: '/path/to/ca.crt' },
  ],

  // ---- MongoDB -----------------------------------------------------------
  mongodb: [
    { key: 'connection_string', label: 'Connection String', type: 'text', required: true, placeholder: 'mongodb://host:27017' },
    { key: 'database', label: 'Database', type: 'text', required: true },
    { key: 'username', label: 'Username', type: 'text' },
    { key: 'password', label: 'Password', type: 'password' },
    { key: 'auth_source', label: 'Auth Source', type: 'text', defaultValue: 'admin' },
  ],

  // ---- S3 ----------------------------------------------------------------
  s3: [
    { key: 'endpoint_url', label: 'Endpoint URL', type: 'text', placeholder: 'https://s3.amazonaws.com' },
    { key: 'region', label: 'Region', type: 'text', required: true, defaultValue: 'us-east-1' },
    { key: 'access_key_id', label: 'Access Key ID', type: 'text', required: true },
    { key: 'secret_access_key', label: 'Secret Access Key', type: 'password', required: true },
    { key: 'bucket', label: 'Bucket', type: 'text' },
  ],

  // ---- HDFS --------------------------------------------------------------
  hdfs: [
    { key: 'namenode_host', label: 'NameNode Host', type: 'text', required: true },
    { key: 'namenode_port', label: 'NameNode Port', type: 'number', required: true, defaultValue: 8020 },
    hadoopAuthType(['NONE', 'KERBEROS']),
    ...kerberosFields,
  ],

  // ---- Kudu --------------------------------------------------------------
  kudu: [
    { key: 'master_addresses', label: 'Master Addresses', type: 'text', required: true, placeholder: 'host1:7051,host2:7051' },
    hadoopAuthType(['NONE', 'KERBEROS']),
    ...kerberosFields,
  ],

  // ---- Unity Catalog -----------------------------------------------------
  unity_catalog: [
    { key: 'api_url', label: 'API URL', type: 'text', required: true, placeholder: 'http://localhost:8080/api/2.1/unity-catalog' },
    {
      key: 'auth_type',
      label: 'Authentication',
      type: 'select',
      required: true,
      defaultValue: 'NONE',
      options: [
        { label: 'None', value: 'NONE' },
        { label: 'Token', value: 'TOKEN' },
        { label: 'OAuth', value: 'OAUTH' },
      ],
    },
    { key: 'token', label: 'Token', type: 'password', placeholder: 'Personal access token', showWhen: { field: 'auth_type', value: 'TOKEN' } },
    { key: 'oauth_client_id', label: 'OAuth Client ID', type: 'text', showWhen: { field: 'auth_type', value: 'OAUTH' } },
    { key: 'oauth_client_secret', label: 'OAuth Client Secret', type: 'password', showWhen: { field: 'auth_type', value: 'OAUTH' } },
  ],
}

// ---------------------------------------------------------------------------
// Utility: build a default-values map for a given platform
// ---------------------------------------------------------------------------

export function getDefaultConfig(platformName: string): Record<string, unknown> {
  const fields = PLATFORM_CONFIGS[platformName]
  if (!fields) return {}

  const defaults: Record<string, unknown> = {}
  const seen = new Set<string>()

  for (const field of fields) {
    // Skip duplicates (e.g. kafka SASL fields duplicated for two protocols)
    if (seen.has(field.key)) continue
    seen.add(field.key)

    if (field.defaultValue !== undefined) {
      defaults[field.key] = field.defaultValue
    }
  }

  return defaults
}
