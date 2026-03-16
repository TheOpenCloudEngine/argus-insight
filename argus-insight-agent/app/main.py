"""Argus Server Agent - FastAPI application entry point."""

import argparse
import logging
import sys
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
from app.heartbeat.scheduler import heartbeat_scheduler
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
    """Print startup banner with version and config paths."""
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info("Config Properties : %s", settings.config_properties_path)
    logger.info("Config Server Properties : %s", settings.config_server_properties_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    _print_banner()
    logger.info("Argus Server Agent %s starting", __version__)
    await metrics_scheduler.start()
    await heartbeat_scheduler.start()
    yield
    await heartbeat_scheduler.stop()
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
    parser = argparse.ArgumentParser(
        prog="argus-insight-agent",
        description="Argus Insight Agent - Server management agent for Argus Insight platform.",
        epilog=(
            "examples:\n"
            "  argus-insight-agent\n"
            "  argus-insight-agent --config-yaml /opt/config/config.yml\n"
            "  argus-insight-agent --config-properties /opt/config/config.properties\n"
            "  argus-insight-agent --config-server-properties /opt/config/server.properties\n"
            "  argus-insight-agent --config-yaml ./config.yml --config-properties ./config.properties"
            " --config-server-properties ./server.properties\n"
            "\n"
            "If no options are specified, configuration files are loaded from\n"
            "/etc/argus-insight-agent/ (or the ARGUS_CONFIG_DIR environment variable)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config-yaml",
        metavar="PATH",
        help=(
            "path to the YAML configuration file (config.yml). "
            "This file defines the main application settings using "
            "Spring Boot style ${variable:default} placeholders. "
            "(default: /etc/argus-insight-agent/config.yml)"
        ),
    )
    parser.add_argument(
        "--config-properties",
        metavar="PATH",
        help=(
            "path to the properties variable file (config.properties). "
            "This file defines key=value variables referenced by config.yml "
            "for environment-specific values such as host, port, and credentials. "
            "(default: /etc/argus-insight-agent/config.properties)"
        ),
    )
    parser.add_argument(
        "--config-server-properties",
        metavar="PATH",
        help=(
            "path to the server properties file (server.properties). "
            "This file defines the central server address that this agent reports to "
            "for heartbeat and management. "
            "(default: /etc/argus-insight-agent/server.properties)"
        ),
    )
    args = parser.parse_args()

    if args.config_yaml or args.config_properties or args.config_server_properties:
        from app.core.config import init_settings

        init_settings(
            yaml_path=args.config_yaml,
            properties_path=args.config_properties,
            server_properties_path=args.config_server_properties,
        )
    else:
        yaml_exists = settings.config_yaml_path.is_file()
        props_exists = settings.config_properties_path.is_file()
        server_props_exists = settings.config_server_properties_path.is_file()
        if not yaml_exists and not props_exists and not server_props_exists:
            parser.print_help()
            print()
            print(
                f"Error: No configuration files found at default location:\n"
                f"  - {settings.config_yaml_path}\n"
                f"  - {settings.config_properties_path}\n"
                f"  - {settings.config_server_properties_path}\n"
                f"\n"
                f"Specify config file paths with --config-yaml, "
                f"--config-properties, and/or "
                f"--config-server-properties options."
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
