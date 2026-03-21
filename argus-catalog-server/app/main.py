"""Catalog Server - FastAPI application entry point."""

import argparse
import logging
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.catalog.router import router as catalog_router
from app.models.router import router as models_router
from app.models.uc_compat import router as uc_compat_router
from app.usermgr.router import router as usermgr_router
from app.core.config import settings
from app.core.database import Base, close_database, engine, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)
_start_time: float = 0.0

BANNER = r"""
_______                                  _________      _____       ______                  ________
___    |_____________ ____  _________    __  ____/_____ __  /______ ___  /____________ _    __  ___/______________   ______________
__  /| |_  ___/_  __ `/  / / /_  ___/    _  /    _  __ `/  __/  __ `/_  /_  __ \_  __ `/    _____ \_  _ \_  ___/_ | / /  _ \_  ___/
_  ___ |  /   _  /_/ // /_/ /_(__  )     / /___  / /_/ // /_ / /_/ /_  / / /_/ /  /_/ /     ____/ //  __/  /   __ |/ //  __/  /
/_/  |_/_/    _\__, / \__,_/ /____/      \____/  \__,_/ \__/ \__,_/ /_/  \____/_\__, /      /____/ \___//_/    _____/ \___//_/
              /____/                                                           /____/
"""


def _print_banner() -> None:
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info("Config Properties : %s", settings.config_properties_path)
    logger.info("Data Directory    : %s", settings.data_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.monotonic()
    setup_logging()
    _print_banner()
    logger.info("Catalog Server %s starting", __version__)
    await init_database()

    import app.catalog.models  # noqa: F401
    import app.models.models  # noqa: F401
    import app.usermgr.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Seed default data
    from app.core.database import async_session
    from app.catalog.service import seed_platforms, seed_platform_metadata
    from app.usermgr.service import seed_roles

    async with async_session() as session:
        await seed_platforms(session)
        await seed_platform_metadata(session)
        await seed_roles(session)

    yield
    await close_database()
    logger.info("Catalog Server shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(uc_compat_router)  # /api/2.0/mlflow/unity-catalog (no extra prefix)
app.include_router(usermgr_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    uptime_seconds = int(time.monotonic() - _start_time)
    return {
        "status": "ok",
        "service": "argus-catalog-server",
        "uptime": uptime_seconds,
        "version": __version__,
    }


def run() -> None:
    parser = argparse.ArgumentParser(
        prog="argus-catalog-server",
        description="Catalog Server - Data catalog management server for Argus platform.",
    )
    parser.add_argument("--config-yaml", metavar="PATH", help="Path to YAML config file")
    parser.add_argument("--config-properties", metavar="PATH", help="Path to properties file")
    args = parser.parse_args()

    if args.config_yaml or args.config_properties:
        from app.core.config import init_settings
        init_settings(
            yaml_path=args.config_yaml,
            properties_path=args.config_properties,
        )
    else:
        yaml_exists = settings.config_yaml_path.is_file()
        props_exists = settings.config_properties_path.is_file()
        if not yaml_exists and not props_exists:
            parser.print_help()
            print()
            print(
                f"Error: No configuration files found at default location:\n"
                f"  - {settings.config_yaml_path}\n"
                f"  - {settings.config_properties_path}\n"
            )
            sys.exit(1)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
