"""Trino metadata synchronization.

Connects to Trino via the trino Python driver (SQLAlchemy dialect),
iterates over catalogs → schemas → tables, and collects column metadata
from information_schema. Stores SHOW CREATE TABLE output in properties
to preserve partition/bucket information that varies by connector.

Trino is a multi-catalog query engine — each catalog maps to a connector
(hive, iceberg, mysql, postgresql, etc.).
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

_TRINO_TYPE_MAP = {
    "boolean": "BOOLEAN",
    "tinyint": "TINYINT",
    "smallint": "SMALLINT",
    "integer": "INT",
    "bigint": "BIGINT",
    "real": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL",
    "varchar": "VARCHAR",
    "char": "CHAR",
    "varbinary": "BINARY",
    "date": "DATE",
    "time": "TIME",
    "time with time zone": "TIME",
    "timestamp": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMP",
    "json": "JSON",
    "uuid": "UUID",
    "ipaddress": "STRING",
    "interval year to month": "STRING",
    "interval day to second": "STRING",
    "hyperloglog": "STRING",
    "p4hyperloglog": "STRING",
    "qdigest": "STRING",
    "tdigest": "STRING",
    "geometry": "STRING",
    "sphericalgeography": "STRING",
}


class TrinoMetadataSync(BasePlatformSync):
    """Synchronize metadata from Trino to Argus Catalog."""

    platform_name = "trino"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engine: Engine | None = None

    def connect(self) -> bool:
        try:
            s = self.settings
            # Build Trino SQLAlchemy URL
            auth_part = s.trino_username
            if s.trino_password:
                auth_part = f"{s.trino_username}:{s.trino_password}"
            url = (
                f"trino://{auth_part}@{s.trino_host}:{s.trino_port}/"
            )
            connect_args = {"http_scheme": s.trino_http_scheme}
            self._engine = create_engine(
                url, connect_args=connect_args,
                pool_size=2, max_overflow=3, pool_recycle=3600,
            )
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(
                "Connected to Trino at %s://%s:%d",
                s.trino_http_scheme, s.trino_host, s.trino_port,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to Trino: %s", e)
            return False

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def discover(self) -> list[dict]:
        result = []
        with self._engine.connect() as conn:
            for catalog in self._get_catalogs(conn):
                try:
                    schemas = self._get_schemas(conn, catalog)
                except Exception as e:
                    logger.warning("Failed to list schemas in %s: %s", catalog, e)
                    continue
                for schema in schemas:
                    try:
                        tables = self._get_tables(conn, catalog, schema)
                        for t in tables:
                            result.append({
                                "catalog": catalog,
                                "schema": schema,
                                "table": t["table_name"],
                                "qualified_name": f"{catalog}.{schema}.{t['table_name']}",
                                "table_type": self._map_table_type(t["table_type"]),
                                "columns_count": 0,
                                "owner": "",
                            })
                    except Exception as e:
                        logger.warning(
                            "Failed to discover in %s.%s: %s", catalog, schema, e,
                        )
        return result

    def sync(self) -> SyncResult:
        result = SyncResult(platform=self.platform_name)
        platform = self.client.get_platform_by_name(self.platform_name)
        if not platform:
            result.errors.append(
                f"Platform '{self.platform_name}' not found in Argus Catalog"
            )
            result.finished_at = datetime.now()
            return result

        platform_id = platform["id"]
        with self._engine.connect() as conn:
            catalogs = self._get_catalogs(conn)
            logger.info("Syncing %d catalogs from Trino", len(catalogs))

            for catalog in catalogs:
                try:
                    schemas = self._get_schemas(conn, catalog)
                except Exception as e:
                    logger.error("Failed to list schemas in %s: %s", catalog, e)
                    result.errors.append(f"Catalog {catalog}: {e}")
                    continue

                for schema in schemas:
                    try:
                        tables = self._get_tables(conn, catalog, schema)
                    except Exception as e:
                        logger.error(
                            "Failed to list tables in %s.%s: %s",
                            catalog, schema, e,
                        )
                        result.errors.append(f"{catalog}.{schema}: {e}")
                        continue

                    for t in tables:
                        try:
                            self._sync_table(
                                platform_id, catalog, schema, t, conn, result,
                            )
                        except Exception as e:
                            qname = f"{catalog}.{schema}.{t['table_name']}"
                            logger.error("Failed to sync %s: %s", qname, e)
                            result.failed += 1
                            result.errors.append(f"{qname}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "Trino sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _get_catalogs(self, conn) -> list[str]:
        rows = conn.execute(text("SHOW CATALOGS")).fetchall()
        all_catalogs = [row[0] for row in rows]
        if self.settings.trino_catalogs:
            return [c for c in all_catalogs if c in self.settings.trino_catalogs]
        return [
            c for c in all_catalogs
            if c not in self.settings.trino_exclude_catalogs
        ]

    def _get_schemas(self, conn, catalog: str) -> list[str]:
        rows = conn.execute(
            text(f'SELECT schema_name FROM "{catalog}".information_schema.schemata')
        ).fetchall()
        all_schemas = [row[0] for row in rows]
        return [
            s for s in all_schemas
            if s not in self.settings.trino_exclude_schemas
        ]

    def _get_tables(self, conn, catalog: str, schema: str) -> list[dict]:
        rows = conn.execute(
            text(
                f'SELECT table_name, table_type '
                f'FROM "{catalog}".information_schema.tables '
                f"WHERE table_schema = :schema"
            ),
            {"schema": schema},
        ).fetchall()
        return [{"table_name": row[0], "table_type": row[1]} for row in rows]

    def _get_columns(self, conn, catalog: str, schema: str, table: str) -> list[dict]:
        rows = conn.execute(
            text(
                f'SELECT column_name, data_type, is_nullable, comment '
                f'FROM "{catalog}".information_schema.columns '
                f"WHERE table_schema = :schema AND table_name = :table "
                f"ORDER BY ordinal_position"
            ),
            {"schema": schema, "table": table},
        ).fetchall()
        return [
            {
                "name": row[0],
                "data_type": row[1],
                "nullable": row[2],
                "comment": row[3],
            }
            for row in rows
        ]

    def _get_table_comment(self, conn, catalog: str, schema: str, table: str) -> str:
        try:
            rows = conn.execute(
                text(
                    "SELECT comment FROM system.metadata.table_comments "
                    "WHERE catalog_name = :catalog AND schema_name = :schema "
                    "AND table_name = :table"
                ),
                {"catalog": catalog, "schema": schema, "table": table},
            ).fetchall()
            if rows and rows[0][0]:
                return rows[0][0]
        except Exception:
            pass
        return ""

    def _get_create_table_ddl(self, conn, catalog: str, schema: str, table: str) -> str:
        try:
            rows = conn.execute(
                text(f'SHOW CREATE TABLE "{catalog}"."{schema}"."{table}"')
            ).fetchall()
            if rows:
                return rows[0][0]
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Type mapping
    # ------------------------------------------------------------------

    def _map_trino_type(self, data_type: str) -> str:
        """Map Trino data_type to normalized catalog type.

        Handles complex types:
        - array(varchar)      → ARRAY<VARCHAR>
        - map(varchar,bigint) → MAP<VARCHAR,BIGINT>
        - row(a varchar, b integer) → STRUCT<a:VARCHAR,b:INT>
        """
        t = data_type.strip()
        lower = t.lower()

        # Complex types
        if lower.startswith("array(") and t.endswith(")"):
            inner = t[6:-1]
            return f"ARRAY<{self._map_trino_type(inner)}>"
        if lower.startswith("map(") and t.endswith(")"):
            inner = t[4:-1]
            key, value = self._split_top_level(inner, ",")
            return f"MAP<{self._map_trino_type(key)},{self._map_trino_type(value)}>"
        if lower.startswith("row(") and t.endswith(")"):
            inner = t[4:-1]
            fields = self._split_top_level_all(inner, ",")
            mapped = []
            for field in fields:
                field = field.strip()
                parts = field.split(None, 1)
                if len(parts) == 2:
                    fname, ftype = parts
                    mapped.append(f"{fname}:{self._map_trino_type(ftype)}")
                else:
                    mapped.append(self._map_trino_type(field))
            return f"STRUCT<{','.join(mapped)}>"

        # Simple types: strip precision
        base = lower.split("(")[0].strip()
        mapped = _TRINO_TYPE_MAP.get(base)
        if mapped:
            return mapped
        return base.upper()

    @staticmethod
    def _split_top_level(s: str, sep: str) -> tuple[str, str]:
        depth = 0
        for i, ch in enumerate(s):
            if ch in ("(", "<"):
                depth += 1
            elif ch in (")", ">"):
                depth -= 1
            elif ch == sep and depth == 0:
                return s[:i].strip(), s[i + 1:].strip()
        return s.strip(), ""

    @staticmethod
    def _split_top_level_all(s: str, sep: str) -> list[str]:
        parts = []
        depth = 0
        start = 0
        for i, ch in enumerate(s):
            if ch in ("(", "<"):
                depth += 1
            elif ch in (")", ">"):
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append(s[start:i].strip())
                start = i + 1
        parts.append(s[start:].strip())
        return parts

    @staticmethod
    def _map_table_type(table_type: str) -> str:
        if table_type == "VIEW":
            return "VIEW"
        return "TABLE"

    # ------------------------------------------------------------------
    # Sync logic
    # ------------------------------------------------------------------

    def _sync_table(
        self, platform_id, catalog, schema, table_info, conn, result,
    ):
        table_name = table_info["table_name"]
        qualified_name = f"{catalog}.{schema}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.trino_origin)

        table_type = self._map_table_type(table_info["table_type"])
        description = self._get_table_comment(conn, catalog, schema, table_name)

        # Columns
        columns = self._get_columns(conn, catalog, schema, table_name)
        schema_fields = []
        for ordinal, col in enumerate(columns):
            schema_fields.append({
                "field_path": col["name"],
                "field_type": self._map_trino_type(col["data_type"]),
                "native_type": col["data_type"],
                "description": col["comment"] or "",
                "nullable": str(col["nullable"] == "YES").lower(),
                "ordinal": ordinal,
            })

        # Properties
        properties = {"trino.catalog": catalog}
        ddl = self._get_create_table_ddl(conn, catalog, schema, table_name)
        if ddl:
            properties["trino.create_table_ddl"] = ddl

        existing = self.client.get_dataset_by_urn(urn)
        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s", qualified_name)
        else:
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.trino_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "schema_fields": schema_fields,
                "owners": [],
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)
