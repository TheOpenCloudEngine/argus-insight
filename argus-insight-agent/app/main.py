"""Argus Server Agent - FastAPI application entry point."""

import argparse
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app import __version__
from app.certmgr.router import router as certmgr_router
from app.command.router import router as command_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.filemgr.router import router as filemgr_router
from app.hostmgr.router import router as hostmgr_router
from app.metrics.scheduler import metrics_scheduler
from app.monitor.router import router as monitor_router
from app.package.router import router as package_router
from app.processmgr.router import router as processmgr_router
from app.sysmon.router import router as sysmon_router
from app.terminal.router import router as terminal_router
from app.terminal.service import terminal_manager
from app.usermgr.router import router as usermgr_router
from app.yum.router import router as yum_router

logger = logging.getLogger(__name__)

BANNER = r"""
_______                                  ________             _____        ______ _____     _______                    _____
___    |_____________ ____  _________    ____  _/________________(_)______ ___  /___  /_    ___    |______ ______________  /_
__  /| |_  ___/_  __ `/  / / /_  ___/     __  / __  __ \_  ___/_  /__  __ `/_  __ \  __/    __  /| |_  __ `/  _ \_  __ \  __/
_  ___ |  /   _  /_/ // /_/ /_(__  )     __/ /  _  / / /(__  )_  / _  /_/ /_  / / / /_      _  ___ |  /_/ //  __/  / / / /_
/_/  |_/_/    _\__, / \__,_/ /____/      /___/  /_/ /_//____/ /_/  _\__, / /_/ /_/\__/      /_/  |_|\__, / \___//_/ /_/\__/
              /____/                                               /____/                          /____/
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
    logger.info("Argus Server Agent %s starting", __version__)
    await metrics_scheduler.start()
    yield
    await metrics_scheduler.stop()
    logger.info("Argus Server Agent shutting down")
    terminal_manager.close_all()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Routers
app.include_router(command_router, prefix="/api/v1")
app.include_router(monitor_router, prefix="/api/v1")
app.include_router(package_router, prefix="/api/v1")
app.include_router(terminal_router, prefix="/api/v1")
app.include_router(sysmon_router, prefix="/api/v1")
app.include_router(yum_router, prefix="/api/v1")
app.include_router(hostmgr_router, prefix="/api/v1")
app.include_router(usermgr_router, prefix="/api/v1")
app.include_router(certmgr_router, prefix="/api/v1")
app.include_router(filemgr_router, prefix="/api/v1")
app.include_router(processmgr_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


def run() -> None:
    """CLI entry point with config file argument support."""
    parser = argparse.ArgumentParser(description="Argus Insight Agent")
    parser.add_argument(
        "--config-yaml",
        metavar="PATH",
        help="Path to config.yml file (default: /etc/argus-insight-agent/config.yml)",
    )
    parser.add_argument(
        "--config-properties",
        metavar="PATH",
        help="Path to config.properties file (default: /etc/argus-insight-agent/config.properties)",
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
