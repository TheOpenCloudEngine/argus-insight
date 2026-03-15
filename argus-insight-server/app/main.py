"""Argus Insight Server - FastAPI application entry point."""

import argparse
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.router import router as agent_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import close_database, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.dashboard.router import router as dashboard_router
from app.proxy.router import router as proxy_router

logger = logging.getLogger(__name__)

BANNER = r"""
_______                                  ________             _____        ______ _____     ________
___    |_____________ ____  _________    ____  _/________________(_)______ ___  /___  /_    __  ___/______________   ______________
__  /| |_  ___/_  __ `/  / / /_  ___/     __  / __  __ \_  ___/_  /__  __ `/_  __ \  __/    _____ \_  _ \_  ___/_ | / /  _ \_  ___/
_  ___ |  /   _  /_/ // /_/ /_(__  )     __/ /  _  / / /(__  )_  / _  /_/ /_  / / / /_      ____/ //  __/  /   __ |/ //  __/  /
/_/  |_/_/    _\__, / \__,_/ /____/      /___/  /_/ /_//____/ /_/  _\__, / /_/ /_/\__/      /____/ \___//_/    _____/ \___//_/
              /____/                                               /____/
"""


def _print_banner() -> None:
    """Print startup banner with version."""
    print(BANNER)
    print(f"Version : {settings.app_version}")
    print()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    _print_banner()
    setup_logging()
    logger.info("Argus Insight Server %s starting", __version__)
    await init_database()
    yield
    await close_database()
    logger.info("Argus Insight Server shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(proxy_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


def run() -> None:
    """CLI entry point with config file argument support."""
    parser = argparse.ArgumentParser(description="Argus Insight Server")
    parser.add_argument(
        "--config-yaml",
        metavar="PATH",
        help="Path to config.yml file (default: /etc/argus-insight-server/config.yml)",
    )
    parser.add_argument(
        "--config-properties",
        metavar="PATH",
        help="Path to config.properties file (default: /etc/argus-insight-server/config.properties)",
    )
    args = parser.parse_args()

    if args.config_yaml or args.config_properties:
        from app.core.config import init_settings

        init_settings(
            yaml_path=args.config_yaml,
            properties_path=args.config_properties,
        )

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
