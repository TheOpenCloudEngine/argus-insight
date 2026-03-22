"""REST API for managing metadata sync remotely."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sync.core.catalog_client import CatalogClient
from sync.core.config import settings
from sync.core.database import init_db
from sync.core.scheduler import SyncScheduler
from sync import __version__
from sync.platforms.hive.query_history import HiveQueryEvent, save_query_event
from sync.platforms.hive.sync import HiveMetastoreSync

logger = logging.getLogger(__name__)

# Global state
_scheduler = SyncScheduler()
_impala_scheduler = None
_start_time: float = 0.0


def _init_platforms() -> None:
    """Initialize and register all enabled platform syncs."""
    global _impala_scheduler
    client = CatalogClient(settings)

    # Hive
    if settings.hive_enabled:
        hive_sync = HiveMetastoreSync(client, settings)
        _scheduler.register(
            hive_sync,
            interval_minutes=settings.hive_schedule_interval_minutes,
            enabled=settings.hive_schedule_enabled,
        )

    # Kudu
    if settings.kudu_enabled:
        from sync.platforms.kudu.sync import KuduMetadataSync

        kudu_sync = KuduMetadataSync(client, settings)
        _scheduler.register(
            kudu_sync,
            interval_minutes=settings.kudu_schedule_interval_minutes,
            enabled=settings.kudu_schedule_enabled,
        )

    # Impala (query collection via Cloudera Manager API)
    if settings.impala_enabled:
        from sync.platforms.impala.collector import ImpalaQueryCollector
        from sync.platforms.impala.scheduler import ImpalaCollectorScheduler

        collector = ImpalaQueryCollector(
            cm_host=settings.impala_cm_host,
            cm_port=settings.impala_cm_port,
            cm_username=settings.impala_cm_username,
            cm_password=settings.impala_cm_password,
            cluster_name=settings.impala_cm_cluster_name,
            service_name=settings.impala_cm_service_name,
            platform_id=settings.impala_platform_id,
            tls_enabled=settings.impala_cm_tls_enabled,
            tls_verify=settings.impala_cm_tls_verify,
            api_version=settings.impala_cm_api_version,
        )
        _impala_scheduler = ImpalaCollectorScheduler(
            collector=collector,
            interval_minutes=settings.impala_schedule_interval_minutes,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.monotonic()
    init_db(settings)
    _init_platforms()
    _scheduler.start()
    if _impala_scheduler and settings.impala_schedule_enabled:
        _impala_scheduler.start()
    yield
    if _impala_scheduler:
        _impala_scheduler.stop()
    _scheduler.stop()


app = FastAPI(
    title="Argus Catalog Metadata Sync",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint."""
    uptime_seconds = int(time.monotonic() - _start_time)
    return {
        "status": "ok",
        "service": "argus-catalog-metadata-sync",
        "uptime": uptime_seconds,
        "version": __version__,
    }


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/sync/status")
async def get_all_status():
    """Get sync status for all registered platforms."""
    return _scheduler.get_all_status()


@app.get("/sync/{platform}/status")
async def get_platform_status(platform: str):
    """Get sync status for a specific platform."""
    status = _scheduler.get_status(platform)
    if not status["registered"]:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' is not registered")
    return status


# ---------------------------------------------------------------------------
# Trigger sync
# ---------------------------------------------------------------------------

@app.post("/sync/{platform}/run")
async def trigger_sync(platform: str):
    """Trigger an immediate metadata sync for a platform."""
    result = _scheduler.run_now(platform)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' is not registered")
    return result.to_dict()


# ---------------------------------------------------------------------------
# Discover
# ---------------------------------------------------------------------------

@app.get("/sync/{platform}/discover")
async def discover(platform: str):
    """Discover available tables from a platform without syncing."""
    if platform not in _scheduler._syncs:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' is not registered")
    sync = _scheduler._syncs[platform]
    try:
        if not sync.connect():
            raise HTTPException(status_code=502, detail="Failed to connect to data source")
        tables = sync.discover()
        return {"platform": platform, "tables": tables, "count": len(tables)}
    finally:
        sync.disconnect()


# ---------------------------------------------------------------------------
# Schedule configuration
# ---------------------------------------------------------------------------

class ScheduleUpdate(BaseModel):
    interval_minutes: int
    enabled: bool


@app.put("/sync/{platform}/schedule")
async def update_schedule(platform: str, req: ScheduleUpdate):
    """Update the sync schedule for a platform."""
    if not _scheduler.update_schedule(platform, req.interval_minutes, req.enabled):
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' is not registered")

    return {
        "status": "ok",
        "platform": platform,
        "interval_minutes": req.interval_minutes,
        "enabled": req.enabled,
    }


@app.get("/sync/{platform}/schedule")
async def get_schedule(platform: str):
    """Get the current sync schedule for a platform."""
    if platform == "hive":
        return {
            "platform": platform,
            "interval_minutes": settings.hive_schedule_interval_minutes,
            "enabled": settings.hive_schedule_enabled,
        }
    elif platform == "kudu":
        return {
            "platform": platform,
            "interval_minutes": settings.kudu_schedule_interval_minutes,
            "enabled": settings.kudu_schedule_enabled,
        }
    raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")


# ---------------------------------------------------------------------------
# Connection configuration
# ---------------------------------------------------------------------------

class HiveConnectionUpdate(BaseModel):
    metastore_host: str
    metastore_port: int = 9083
    kerberos_enabled: bool = False
    kerberos_principal: str = ""
    kerberos_keytab: str = ""
    databases: list[str] = []
    exclude_databases: list[str] = ["sys", "information_schema"]
    origin: str = "PROD"


@app.put("/sync/hive/connection")
async def update_hive_connection(req: HiveConnectionUpdate):
    """Update the Hive Metastore connection configuration."""
    settings.hive_metastore_host = req.metastore_host
    settings.hive_metastore_port = req.metastore_port
    settings.hive_kerberos_enabled = req.kerberos_enabled
    settings.hive_kerberos_principal = req.kerberos_principal
    settings.hive_kerberos_keytab = req.kerberos_keytab
    settings.hive_databases = req.databases
    settings.hive_exclude_databases = req.exclude_databases
    settings.hive_origin = req.origin

    # Re-register with new config
    client = CatalogClient(settings)
    hive_sync = HiveMetastoreSync(client, settings)
    _scheduler.register(
        hive_sync,
        interval_minutes=settings.hive_schedule_interval_minutes,
        enabled=settings.hive_schedule_enabled,
    )

    return {"status": "ok", "message": "Hive connection updated"}


@app.post("/sync/hive/test")
async def test_hive_connection():
    """Test connection to Hive Metastore."""
    client = CatalogClient(settings)
    hive_sync = HiveMetastoreSync(client, settings)
    try:
        connected = hive_sync.connect()
        if connected:
            dbs = hive_sync.discover()
            db_names = list({d["database"] for d in dbs})
            return {
                "status": "ok",
                "message": "Connection successful",
                "databases": sorted(db_names),
                "tables_count": len(dbs),
            }
        return {"status": "error", "message": "Failed to connect"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        hive_sync.disconnect()


# ---------------------------------------------------------------------------
# Kudu connection configuration
# ---------------------------------------------------------------------------

class KuduConnectionUpdate(BaseModel):
    master_addresses: str = "localhost:7051"
    table_filter: str = ""
    default_database: str = "default"
    parse_impala_naming: bool = True
    origin: str = "PROD"
    kerberos_enabled: bool = False
    kerberos_principal: str = ""
    kerberos_keytab: str = ""
    sasl_protocol_name: str = "kudu"
    require_authentication: bool = False
    encryption_policy: str = "optional"
    trusted_certificates: list[str] = []


@app.put("/sync/kudu/connection")
async def update_kudu_connection(req: KuduConnectionUpdate):
    """Update the Kudu connection configuration."""
    settings.kudu_master_addresses = req.master_addresses
    settings.kudu_table_filter = req.table_filter
    settings.kudu_default_database = req.default_database
    settings.kudu_parse_impala_naming = req.parse_impala_naming
    settings.kudu_origin = req.origin
    settings.kudu_kerberos_enabled = req.kerberos_enabled
    settings.kudu_kerberos_principal = req.kerberos_principal
    settings.kudu_kerberos_keytab = req.kerberos_keytab
    settings.kudu_sasl_protocol_name = req.sasl_protocol_name
    settings.kudu_require_authentication = req.require_authentication
    settings.kudu_encryption_policy = req.encryption_policy
    settings.kudu_trusted_certificates = req.trusted_certificates

    # Re-register with new config
    from sync.platforms.kudu.sync import KuduMetadataSync

    client = CatalogClient(settings)
    kudu_sync = KuduMetadataSync(client, settings)
    _scheduler.register(
        kudu_sync,
        interval_minutes=settings.kudu_schedule_interval_minutes,
        enabled=settings.kudu_schedule_enabled,
    )

    return {"status": "ok", "message": "Kudu connection updated"}


@app.post("/sync/kudu/test")
async def test_kudu_connection():
    """Test connection to Kudu master(s)."""
    from sync.platforms.kudu.sync import KuduMetadataSync

    client = CatalogClient(settings)
    kudu_sync = KuduMetadataSync(client, settings)
    try:
        connected = kudu_sync.connect()
        if connected:
            tables = kudu_sync.discover()
            return {
                "status": "ok",
                "message": "Connection successful",
                "tables_count": len(tables),
            }
        return {"status": "error", "message": "Failed to connect"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        kudu_sync.disconnect()


# ---------------------------------------------------------------------------
# Hive Query History Collection
# ---------------------------------------------------------------------------

@app.post("/collector/hive/query")
async def collect_hive_query(event: HiveQueryEvent):
    """Receive a Hive query audit event from QueryAuditHook and save it immediately."""
    try:
        record = save_query_event(event)
        lineage_count = 0

        # Parse lineage for successful queries that have SQL text
        if event.status == "SUCCESS" and event.query:
            try:
                from sync.platforms.hive.lineage_service import process_query_lineage

                lineage_records = process_query_lineage(
                    query_hist_id=record.id,
                    query_id=event.queryId,
                    sql=event.query,
                    hook_inputs=event.inputs,
                    hook_outputs=event.outputs,
                )
                lineage_count = len(lineage_records)
            except Exception as e:
                # Lineage failure should not block query history collection
                logger.warning("Lineage parsing failed for query %s: %s", event.queryId, e)

        return {
            "status": "ok",
            "id": record.id,
            "queryId": record.query_id,
            "lineageCount": lineage_count,
        }
    except Exception as e:
        logger.error("Failed to save Hive query event: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save query event: {e}")


# ---------------------------------------------------------------------------
# Impala Query Collection (from Java Agent)
# ---------------------------------------------------------------------------

@app.post("/collector/impala/query")
async def collect_impala_query(event: dict):
    """Receive an Impala query event from the Java Agent and save it immediately."""
    from sync.platforms.impala.query_history import ImpalaQueryEvent, save_impala_query_event

    try:
        parsed_event = ImpalaQueryEvent(**event)
        record = save_impala_query_event(parsed_event)
        lineage_count = 0

        # Parse lineage if query text is available
        if record.statement:
            try:
                from sync.platforms.impala.lineage_service import process_impala_query_lineage
                lineage_count = process_impala_query_lineage(record)
            except Exception as e:
                logger.warning("Impala lineage parsing failed for query %s: %s", record.query_id, e)

        return {
            "status": "ok",
            "id": record.id,
            "queryId": record.query_id,
            "lineageCount": lineage_count,
        }
    except Exception as e:
        logger.error("Failed to save Impala query event: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save query event: {e}")


# ---------------------------------------------------------------------------
# Trino Query Collection (from EventListener plugin)
# ---------------------------------------------------------------------------

@app.post("/collector/trino/query")
async def collect_trino_query(event: dict):
    """Receive a Trino query event from the EventListener plugin."""
    from sync.platforms.trino.query_history import save_trino_query_event, save_trino_lineage

    try:
        record = save_trino_query_event(event)
        lineage_count = 0

        # Trino provides native input/output metadata — no SQL parsing needed
        if record.query_state == "FINISHED":
            try:
                lineage_count = save_trino_lineage(record)
            except Exception as e:
                logger.warning("Trino lineage failed for query %s: %s", record.query_id, e)

        return {
            "status": "ok",
            "id": record.id,
            "queryId": record.query_id,
            "lineageCount": lineage_count,
        }
    except Exception as e:
        logger.error("Failed to save Trino query event: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save query event: {e}")


# ---------------------------------------------------------------------------
# StarRocks Query Collection (from AuditPlugin)
# ---------------------------------------------------------------------------

@app.post("/collector/starrocks/query")
async def collect_starrocks_query(event: dict):
    """Receive a StarRocks query event from the AuditPlugin."""
    from sync.platforms.starrocks.query_history import save_starrocks_query_event

    try:
        record = save_starrocks_query_event(event)
        return {
            "status": "ok",
            "id": record.id,
            "queryId": record.query_id,
        }
    except Exception as e:
        logger.error("Failed to save StarRocks query event: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save query event: {e}")
