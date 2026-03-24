"""Data Engineer AI Agent - FastAPI application entry point."""

import argparse
import logging
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import settings
from app.core.database import Base, close_database, engine, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.router.chat import router as chat_router
from app.router.chat import set_engine
from app.router.settings import router as settings_router

logger = logging.getLogger(__name__)
_start_time: float = 0.0

BANNER = r"""
_______                                  ______ _______    ___                    _____
___    |_____________ ____  _________    ___  / ___  __    ___  ______ ____________  /_
__  /| |_  ___/_  __ `/  / / /_  ___/    __  /  __  __    __  /  __  /_  __ \  _ \_  __/
_  ___ |  /   _  /_/ // /_/ /_(__  )     _  /___  /___    _  /___  /_/ /  / / /  __/  /_
/_/  |_/_/    _\__, / \__,_/ /____/      /_____/______/   /_____/\__, / /_/ /_/\___/\__/
              /____/                                            /____/
              Data Engineer AI Agent
"""


def _print_banner() -> None:
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info("Config Properties : %s", settings.config_properties_path)
    logger.info("Catalog URL       : %s", settings.catalog_base_url)
    logger.info("LLM Provider      : %s (%s)", settings.llm_provider, settings.llm_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.monotonic()
    setup_logging()
    _print_banner()
    logger.info("DE Agent %s starting", __version__)

    # Initialize database
    await init_database()

    import app.models.conversation  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Initialize LLM provider
    from app.llm.registry import initialize_from_settings

    try:
        llm = await initialize_from_settings()
        logger.info("LLM provider ready")
    except Exception as e:
        logger.warning("LLM provider initialization failed: %s", e)
        logger.warning(
            "Agent will not be functional until LLM is configured via /api/v1/settings/llm"
        )
        llm = None

    # Create catalog client and tool registry
    from app.catalog_client.client import CatalogClient
    from app.tools.setup import create_tool_registry

    catalog = CatalogClient()
    tool_registry = create_tool_registry(catalog)
    logger.info("Tool registry ready: %d tools registered", len(tool_registry))

    # Create and set the agent engine
    if llm:
        from app.agent.engine import AgentEngine

        agent_engine = AgentEngine(llm=llm, tool_registry=tool_registry)
        set_engine(agent_engine)
        logger.info("Agent engine ready")

    yield

    # Shutdown
    from app.llm.registry import shutdown_provider

    await shutdown_provider()
    await catalog.close()
    await close_database()
    logger.info("DE Agent shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)


class DynamicCORSMiddleware:
    """CORS middleware that reads allowed origins from settings at request time."""

    def __init__(self, app):
        self.app = app
        self._inner = None
        self._origins_snapshot = None

    def _get_inner(self):
        current = tuple(settings.cors_origins)
        if current != self._origins_snapshot:
            self._inner = CORSMiddleware(
                app=self.app,
                allow_origins=list(current),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            self._origins_snapshot = current
        return self._inner

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        await self._get_inner()(scope, receive, send)


app.add_middleware(DynamicCORSMiddleware)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    uptime_seconds = int(time.monotonic() - _start_time)

    from app.llm.registry import get_provider

    provider = await get_provider()

    return {
        "status": "ok",
        "service": "argus-data-engineer-ai-agent",
        "uptime": uptime_seconds,
        "version": __version__,
        "llm": {
            "provider": provider.provider_name() if provider else None,
            "model": provider.model_name() if provider else None,
            "ready": provider is not None,
        },
    }


def run() -> None:
    parser = argparse.ArgumentParser(
        prog="argus-de-agent",
        description="Argus Data Engineer AI Agent - AI-powered assistant for data engineering.",
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
