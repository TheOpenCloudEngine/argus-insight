"""Catalog Server - FastAPI application entry point."""

import argparse
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.catalog.router import router as catalog_router
from app.usermgr.router import router as usermgr_router
from app.core.config import settings
from app.core.database import Base, close_database, engine, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

BANNER = r"""
  ______      __        __                _____
 / ____/___ _/ /_____ _/ /___  ____ _    / ___/___  ______   _____  _____
/ /   / __ `/ __/ __ `/ / __ \/ __ `/    \__ \/ _ \/ ___/ | / / _ \/ ___/
/ /___/ /_/ / /_/ /_/ / / /_/ / /_/ /    ___/ /  __/ /   | |/ /  __/ /
\____/\__,_/\__/\__,_/_/\____/\__, /    /____/\___/_/    |___/\___/_/
                              /____/
"""


def _print_banner() -> None:
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info("Config Properties : %s", settings.config_properties_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _print_banner()
    logger.info("Catalog Server %s starting", __version__)
    await init_database()

    import app.catalog.models  # noqa: F401
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
app.include_router(usermgr_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


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
