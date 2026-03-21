"""REST API for managing metadata sync remotely."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sync.core.catalog_client import CatalogClient
from sync.core.config import load_config, save_config
from sync.core.database import init_db
from sync.core.scheduler import SyncScheduler
from sync.platforms.hive.query_history import HiveQueryEvent, save_query_event
from sync.platforms.hive.sync import HiveMetastoreSync

logger = logging.getLogger(__name__)

# Global state
_config = load_config()
_scheduler = SyncScheduler()


def _init_platforms() -> None:
    """Initialize and register all enabled platform syncs."""
    client = CatalogClient(_config.catalog)

    # Hive
    hive_cfg = _config.platforms.hive
    if hive_cfg.enabled:
        hive_sync = HiveMetastoreSync(client, hive_cfg)
        _scheduler.register(
            hive_sync,
            interval_minutes=hive_cfg.schedule.interval_minutes,
            enabled=hive_cfg.schedule.enabled,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(_config.database.url)
    _init_platforms()
    _scheduler.start()
    yield
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
    return {"status": "ok", "service": "metadata-sync"}


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

    # Persist to config file
    if platform == "hive":
        _config.platforms.hive.schedule.interval_minutes = req.interval_minutes
        _config.platforms.hive.schedule.enabled = req.enabled
    save_config(_config)

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
        sched = _config.platforms.hive.schedule
        return {
            "platform": platform,
            "interval_minutes": sched.interval_minutes,
            "enabled": sched.enabled,
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
    hive = _config.platforms.hive
    hive.metastore_host = req.metastore_host
    hive.metastore_port = req.metastore_port
    hive.kerberos.enabled = req.kerberos_enabled
    hive.kerberos.principal = req.kerberos_principal
    hive.kerberos.keytab = req.kerberos_keytab
    hive.databases = req.databases
    hive.exclude_databases = req.exclude_databases
    hive.origin = req.origin
    save_config(_config)

    # Re-register with new config
    client = CatalogClient(_config.catalog)
    hive_sync = HiveMetastoreSync(client, hive)
    _scheduler.register(
        hive_sync,
        interval_minutes=hive.schedule.interval_minutes,
        enabled=hive.schedule.enabled,
    )

    return {"status": "ok", "message": "Hive connection updated"}


@app.post("/sync/hive/test")
async def test_hive_connection():
    """Test connection to Hive Metastore."""
    client = CatalogClient(_config.catalog)
    hive_sync = HiveMetastoreSync(client, _config.platforms.hive)
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
# Hive Query History Collection
# ---------------------------------------------------------------------------

@app.post("/collector/hive/query")
async def collect_hive_query(event: HiveQueryEvent):
    """Receive a Hive query audit event from QueryAuditHook and save it immediately."""
    try:
        record = save_query_event(event)
        return {
            "status": "ok",
            "id": record.id,
            "queryId": record.query_id,
        }
    except Exception as e:
        logger.error("Failed to save Hive query event: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save query event: {e}")
