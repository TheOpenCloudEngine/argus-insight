"""Argus Insight Server - FastAPI application entry point."""

import argparse
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.disconnect_checker import disconnect_checker
from app.agent.router import router as agent_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import Base, close_database, engine, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.dashboard.router import router as dashboard_router
from app.dns.router import router as dns_router
from app.settings.router import router as settings_router
from app.notes.router import router as notes_router
from app.objectfilemgr.router import router as objectfilemgr_router
from app.proxy.router import router as proxy_router
from app.security.router import router as security_router
from app.servermgr.router import router as servermgr_router
from app.unity_catalog.router import router as unity_catalog_router
from app.usermgr.router import router as usermgr_router
from workspace_provisioner.router import router as workspace_router
from workspace_provisioner.router import init_gitlab_client

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
    """Print startup banner with version and config paths."""
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info("Config Properties : %s", settings.config_properties_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    _print_banner()
    logger.info("Argus Insight Server %s starting", __version__)
    await init_database()
    # Ensure ORM tables exist (import models so they are registered with Base)
    import app.agent.models  # noqa: F401
    import app.settings.models  # noqa: F401
    import app.notes.models  # noqa: F401
    import app.objectfilemgr.models  # noqa: F401
    import app.usermgr.models  # noqa: F401
    import workspace_provisioner.models  # noqa: F401
    import workspace_provisioner.workflow.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Seed default roles
    from app.core.database import async_session
    from app.usermgr.service import seed_roles

    async with async_session() as session:
        await seed_roles(session)

    from app.settings.service import seed_infra_config

    async with async_session() as session:
        await seed_infra_config(session)

    # Initialize GitLab client for workspace provisioner
    if settings.gitlab_url and settings.gitlab_token:
        init_gitlab_client(
            url=settings.gitlab_url,
            private_token=settings.gitlab_token,
        )

    await disconnect_checker.start()
    yield
    await disconnect_checker.stop()
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
app.include_router(dns_router, prefix="/api/v1")
app.include_router(usermgr_router, prefix="/api/v1")
app.include_router(servermgr_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(notes_router, prefix="/api/v1")
app.include_router(objectfilemgr_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(unity_catalog_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


def run() -> None:
    """CLI entry point with config file argument support."""
    parser = argparse.ArgumentParser(
        prog="argus-insight-server",
        description="Argus Insight Server - Central management server for Argus Insight platform.",
        epilog=(
            "examples:\n"
            "  argus-insight-server\n"
            "  argus-insight-server --config-yaml /opt/config/config.yml\n"
            "  argus-insight-server --config-properties /opt/config/config.properties\n"
            "  argus-insight-server --config-yaml ./config.yml --config-properties ./config.properties\n"
            "\n"
            "If no options are specified, configuration files are loaded from\n"
            "/etc/argus-insight-server/ (or the ARGUS_SERVER_CONFIG_DIR environment variable)."
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
            "(default: /etc/argus-insight-server/config.yml)"
        ),
    )
    parser.add_argument(
        "--config-properties",
        metavar="PATH",
        help=(
            "path to the properties variable file (config.properties). "
            "This file defines key=value variables referenced by config.yml "
            "for environment-specific values such as host, port, and credentials. "
            "(default: /etc/argus-insight-server/config.properties)"
        ),
    )
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
                f"\n"
                f"Specify config file paths with --config-yaml and/or "
                f"--config-properties options."
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
