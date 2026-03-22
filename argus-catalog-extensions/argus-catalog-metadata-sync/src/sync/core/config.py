"""Application configuration.

Configuration is loaded from two files in the config directory:
1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}
"""

import os
from pathlib import Path

from sync.core.config_loader import load_config

_CONFIG_DIR = Path(
    os.environ.get("ARGUS_CATALOG_METADATA_SYNC_CONFIG_DIR", "/etc/argus-catalog-metadata-sync")
)
_yaml_path: Path = _CONFIG_DIR / "config.yml"
_properties_path: Path = _CONFIG_DIR / "config.properties"
_raw: dict = load_config(config_dir=_CONFIG_DIR)


def _get(section: str, key: str, default=None):
    return _raw.get(section, {}).get(key, default)


def _get_nested(section: str, subsection: str, key: str, default=None):
    return _raw.get(section, {}).get(subsection, {}).get(key, default)


def _get_deep(section: str, sub1: str, sub2: str, key: str, default=None):
    return _raw.get(section, {}).get(sub1, {}).get(sub2, {}).get(key, default)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


class Settings:
    """Global application settings loaded from config.yml + config.properties."""

    def __init__(self) -> None:
        self.app_name: str = _get("app", "name", "argus-catalog-metadata-sync")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 4610))

        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "argus-catalog-metadata-sync.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

        self.config_dir: Path = _CONFIG_DIR
        self.config_yaml_path: Path = _yaml_path
        self.config_properties_path: Path = _properties_path

        self.cors_origins: list[str] = _get("cors", "origins", ["*"])

        # Database
        self.db_type: str = _get("database", "type", "postgresql")
        self.db_host: str = _get("database", "host", "localhost")
        self.db_port: int = int(_get("database", "port", 5432))
        self.db_name: str = _get("database", "name", "argus_catalog")
        self.db_username: str = _get("database", "username", "argus")
        self.db_password: str = _get("database", "password", "argus")
        self.db_pool_size: int = int(_get_nested("database", "pool", "size", 5))
        self.db_pool_max_overflow: int = int(_get_nested("database", "pool", "max_overflow", 10))
        self.db_pool_recycle: int = int(_get_nested("database", "pool", "recycle", 3600))
        self.db_echo: bool = _to_bool(_get("database", "echo", False))

        # Catalog Server
        self.catalog_base_url: str = _get("catalog", "base_url",
                                          "http://localhost:4600/api/v1/catalog")
        self.catalog_timeout: int = int(_get("catalog", "timeout", 30))

        # Hive Platform
        hive_raw = _raw.get("platforms", {}).get("hive", {})
        self.hive_enabled: bool = _to_bool(hive_raw.get("enabled", True))
        self.hive_metastore_host: str = hive_raw.get("metastore_host", "localhost")
        self.hive_metastore_port: int = int(hive_raw.get("metastore_port", 9083))
        krb = hive_raw.get("kerberos", {})
        self.hive_kerberos_enabled: bool = _to_bool(krb.get("enabled", False))
        self.hive_kerberos_principal: str = krb.get("principal", "")
        self.hive_kerberos_keytab: str = krb.get("keytab", "")
        self.hive_databases: list[str] = hive_raw.get("databases", [])
        self.hive_exclude_databases: list[str] = hive_raw.get(
            "exclude_databases", ["sys", "information_schema"]
        )
        sched = hive_raw.get("schedule", {})
        self.hive_schedule_interval_minutes: int = int(sched.get("interval_minutes", 60))
        self.hive_schedule_enabled: bool = _to_bool(sched.get("enabled", True))
        self.hive_origin: str = hive_raw.get("origin", "PROD")
        self.hive_sync_mode: str = hive_raw.get("sync_mode", "thrift")  # "thrift" or "sql"

        # SQL mode: Hive Metastore backend RDBMS connection
        hive_db = hive_raw.get("metastore_db", {})
        self.hive_metastore_db_type: str = hive_db.get("type", "mysql")
        self.hive_metastore_db_host: str = hive_db.get("host", "localhost")
        self.hive_metastore_db_port: int = int(hive_db.get("port", 3306))
        self.hive_metastore_db_name: str = hive_db.get("name", "hive")
        self.hive_metastore_db_username: str = hive_db.get("username", "hive")
        self.hive_metastore_db_password: str = hive_db.get("password", "hive")

        # Kudu Platform
        kudu_raw = _raw.get("platforms", {}).get("kudu", {})
        self.kudu_enabled: bool = _to_bool(kudu_raw.get("enabled", False))
        self.kudu_master_addresses: str = kudu_raw.get("master_addresses", "localhost:7051")
        self.kudu_table_filter: str = kudu_raw.get("table_filter", "")
        self.kudu_default_database: str = kudu_raw.get("default_database", "default")
        self.kudu_parse_impala_naming: bool = _to_bool(
            kudu_raw.get("parse_impala_naming", True)
        )
        # Kerberos authentication
        krb = kudu_raw.get("kerberos", {})
        self.kudu_kerberos_enabled: bool = _to_bool(krb.get("enabled", False))
        self.kudu_kerberos_principal: str = krb.get("principal", "")
        self.kudu_kerberos_keytab: str = krb.get("keytab", "")
        self.kudu_sasl_protocol_name: str = krb.get("sasl_protocol_name", "kudu")
        # TLS / Encryption
        tls = kudu_raw.get("tls", {})
        self.kudu_require_authentication: bool = _to_bool(tls.get("require_authentication", False))
        self.kudu_encryption_policy: str = tls.get("encryption_policy", "optional")
        self.kudu_trusted_certificates: list[str] = tls.get("trusted_certificates", [])

        self.kudu_origin: str = kudu_raw.get("origin", "PROD")
        kudu_sched = kudu_raw.get("schedule", {})
        self.kudu_schedule_interval_minutes: int = int(
            kudu_sched.get("interval_minutes", 60)
        )
        self.kudu_schedule_enabled: bool = _to_bool(kudu_sched.get("enabled", True))

        # Greenplum Platform
        gp_raw = _raw.get("platforms", {}).get("greenplum", {})
        self.greenplum_enabled: bool = _to_bool(gp_raw.get("enabled", False))
        self.greenplum_host: str = gp_raw.get("host", "localhost")
        self.greenplum_port: int = int(gp_raw.get("port", 5432))
        self.greenplum_database: str = gp_raw.get("database", "")
        self.greenplum_username: str = gp_raw.get("username", "gpadmin")
        self.greenplum_password: str = gp_raw.get("password", "")
        self.greenplum_databases: list[str] = gp_raw.get("databases", [])
        self.greenplum_exclude_databases: list[str] = gp_raw.get(
            "exclude_databases", ["template0", "template1", "postgres"]
        )
        self.greenplum_schemas: list[str] = gp_raw.get("schemas", [])
        self.greenplum_exclude_schemas: list[str] = gp_raw.get(
            "exclude_schemas",
            ["pg_catalog", "information_schema", "gp_toolkit", "pg_toast"],
        )
        self.greenplum_origin: str = gp_raw.get("origin", "PROD")
        gp_sched = gp_raw.get("schedule", {})
        self.greenplum_schedule_interval_minutes: int = int(
            gp_sched.get("interval_minutes", 60)
        )
        self.greenplum_schedule_enabled: bool = _to_bool(
            gp_sched.get("enabled", True)
        )

        # MySQL Platform
        my_raw = _raw.get("platforms", {}).get("mysql", {})
        self.mysql_enabled: bool = _to_bool(my_raw.get("enabled", False))
        self.mysql_host: str = my_raw.get("host", "localhost")
        self.mysql_port: int = int(my_raw.get("port", 3306))
        self.mysql_username: str = my_raw.get("username", "root")
        self.mysql_password: str = my_raw.get("password", "")
        self.mysql_databases: list[str] = my_raw.get("databases", [])
        self.mysql_exclude_databases: list[str] = my_raw.get(
            "exclude_databases",
            ["information_schema", "mysql", "performance_schema", "sys"],
        )
        self.mysql_origin: str = my_raw.get("origin", "PROD")
        my_sched = my_raw.get("schedule", {})
        self.mysql_schedule_interval_minutes: int = int(
            my_sched.get("interval_minutes", 60)
        )
        self.mysql_schedule_enabled: bool = _to_bool(my_sched.get("enabled", True))

        # PostgreSQL Platform
        pg_raw = _raw.get("platforms", {}).get("postgresql", {})
        self.postgresql_enabled: bool = _to_bool(pg_raw.get("enabled", False))
        self.postgresql_host: str = pg_raw.get("host", "localhost")
        self.postgresql_port: int = int(pg_raw.get("port", 5432))
        self.postgresql_database: str = pg_raw.get("database", "")
        self.postgresql_username: str = pg_raw.get("username", "postgres")
        self.postgresql_password: str = pg_raw.get("password", "")
        self.postgresql_databases: list[str] = pg_raw.get("databases", [])
        self.postgresql_exclude_databases: list[str] = pg_raw.get(
            "exclude_databases", ["template0", "template1", "postgres"]
        )
        self.postgresql_schemas: list[str] = pg_raw.get("schemas", [])
        self.postgresql_exclude_schemas: list[str] = pg_raw.get(
            "exclude_schemas", ["pg_catalog", "information_schema", "pg_toast"],
        )
        self.postgresql_origin: str = pg_raw.get("origin", "PROD")
        pg_sched = pg_raw.get("schedule", {})
        self.postgresql_schedule_interval_minutes: int = int(
            pg_sched.get("interval_minutes", 60)
        )
        self.postgresql_schedule_enabled: bool = _to_bool(pg_sched.get("enabled", True))

        # Oracle Platform
        ora_raw = _raw.get("platforms", {}).get("oracle", {})
        self.oracle_enabled: bool = _to_bool(ora_raw.get("enabled", False))
        self.oracle_host: str = ora_raw.get("host", "localhost")
        self.oracle_port: int = int(ora_raw.get("port", 1521))
        self.oracle_service_name: str = ora_raw.get("service_name", "")
        self.oracle_sid: str = ora_raw.get("sid", "ORCL")
        self.oracle_username: str = ora_raw.get("username", "system")
        self.oracle_password: str = ora_raw.get("password", "")
        self.oracle_schemas: list[str] = ora_raw.get("schemas", [])
        self.oracle_exclude_schemas: list[str] = ora_raw.get(
            "exclude_schemas",
            ["SYS", "SYSTEM", "DBSNMP", "APPQOSSYS", "OUTLN", "XDB",
             "WMSYS", "CTXSYS", "MDSYS", "ORDDATA", "ORDSYS", "OLAPSYS"],
        )
        self.oracle_origin: str = ora_raw.get("origin", "PROD")
        ora_sched = ora_raw.get("schedule", {})
        self.oracle_schedule_interval_minutes: int = int(
            ora_sched.get("interval_minutes", 60)
        )
        self.oracle_schedule_enabled: bool = _to_bool(ora_sched.get("enabled", True))

        # MSSQL Platform
        ms_raw = _raw.get("platforms", {}).get("mssql", {})
        self.mssql_enabled: bool = _to_bool(ms_raw.get("enabled", False))
        self.mssql_host: str = ms_raw.get("host", "localhost")
        self.mssql_port: int = int(ms_raw.get("port", 1433))
        self.mssql_database: str = ms_raw.get("database", "")
        self.mssql_username: str = ms_raw.get("username", "sa")
        self.mssql_password: str = ms_raw.get("password", "")
        self.mssql_databases: list[str] = ms_raw.get("databases", [])
        self.mssql_exclude_databases: list[str] = ms_raw.get(
            "exclude_databases", ["master", "tempdb", "model", "msdb"],
        )
        self.mssql_schemas: list[str] = ms_raw.get("schemas", [])
        self.mssql_origin: str = ms_raw.get("origin", "PROD")
        ms_sched = ms_raw.get("schedule", {})
        self.mssql_schedule_interval_minutes: int = int(
            ms_sched.get("interval_minutes", 60)
        )
        self.mssql_schedule_enabled: bool = _to_bool(ms_sched.get("enabled", True))

        # Trino Platform (metadata sync)
        tr_raw = _raw.get("platforms", {}).get("trino", {})
        self.trino_sync_enabled: bool = _to_bool(tr_raw.get("enabled", False))
        self.trino_host: str = tr_raw.get("host", "localhost")
        self.trino_port: int = int(tr_raw.get("port", 8080))
        self.trino_username: str = tr_raw.get("username", "trino")
        self.trino_password: str = tr_raw.get("password", "")
        self.trino_http_scheme: str = tr_raw.get("http_scheme", "https")
        self.trino_catalogs: list[str] = tr_raw.get("catalogs", [])
        self.trino_exclude_catalogs: list[str] = tr_raw.get(
            "exclude_catalogs", ["system", "jmx"]
        )
        self.trino_exclude_schemas: list[str] = tr_raw.get(
            "exclude_schemas", ["information_schema"]
        )
        self.trino_origin: str = tr_raw.get("origin", "PROD")
        tr_sched = tr_raw.get("schedule", {})
        self.trino_schedule_interval_minutes: int = int(
            tr_sched.get("interval_minutes", 60)
        )
        self.trino_schedule_enabled: bool = _to_bool(tr_sched.get("enabled", True))

        # StarRocks Platform (metadata sync)
        sr_raw = _raw.get("platforms", {}).get("starrocks", {})
        self.starrocks_sync_enabled: bool = _to_bool(sr_raw.get("enabled", False))
        self.starrocks_host: str = sr_raw.get("host", "localhost")
        self.starrocks_port: int = int(sr_raw.get("port", 9030))
        self.starrocks_username: str = sr_raw.get("username", "root")
        self.starrocks_password: str = sr_raw.get("password", "")
        self.starrocks_databases: list[str] = sr_raw.get("databases", [])
        self.starrocks_exclude_databases: list[str] = sr_raw.get(
            "exclude_databases",
            ["information_schema", "_statistics_", "starrocks_monitor"],
        )
        self.starrocks_origin: str = sr_raw.get("origin", "PROD")
        sr_sched = sr_raw.get("schedule", {})
        self.starrocks_schedule_interval_minutes: int = int(
            sr_sched.get("interval_minutes", 60)
        )
        self.starrocks_schedule_enabled: bool = _to_bool(
            sr_sched.get("enabled", True)
        )

        # Impala Platform (query collection via Cloudera Manager API)
        impala_raw = _raw.get("platforms", {}).get("impala", {})
        self.impala_enabled: bool = _to_bool(impala_raw.get("enabled", False))
        self.impala_platform_id: str = impala_raw.get("platform_id", "")
        cm = impala_raw.get("cloudera_manager", {})
        self.impala_cm_host: str = cm.get("host", "localhost")
        self.impala_cm_port: int = int(cm.get("port", 7180))
        self.impala_cm_username: str = cm.get("username", "admin")
        self.impala_cm_password: str = cm.get("password", "admin")
        self.impala_cm_cluster_name: str = cm.get("cluster_name", "cluster")
        self.impala_cm_service_name: str = cm.get("service_name", "impala")
        self.impala_cm_api_version: int = int(cm.get("api_version", 19))
        tls = cm.get("tls", {})
        self.impala_cm_tls_enabled: bool = _to_bool(tls.get("enabled", False))
        self.impala_cm_tls_verify: bool = _to_bool(tls.get("verify", True))
        impala_sched = impala_raw.get("schedule", {})
        self.impala_schedule_interval_minutes: int = int(
            impala_sched.get("interval_minutes", 5)
        )
        self.impala_schedule_enabled: bool = _to_bool(impala_sched.get("enabled", True))

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy database URL from config."""
        if self.db_type == "postgresql":
            return (
                f"postgresql://{self.db_username}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        elif self.db_type == "mariadb" or self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.db_username}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        else:
            return f"sqlite:///{self.db_name}"


def init_settings(
    yaml_path: str | None = None,
    properties_path: str | None = None,
) -> None:
    """Re-initialize settings with custom config file paths."""
    global _raw, _yaml_path, _properties_path
    if yaml_path:
        _yaml_path = Path(yaml_path)
    if properties_path:
        _properties_path = Path(properties_path)
    _raw = load_config(
        config_dir=_CONFIG_DIR,
        yaml_path=yaml_path,
        properties_path=properties_path,
    )
    settings.__init__()


settings = Settings()
