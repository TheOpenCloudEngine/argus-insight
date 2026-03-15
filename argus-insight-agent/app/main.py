"""Argus Server Agent - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.command.router import router as command_router
from app.monitor.router import router as monitor_router
from app.package.router import router as package_router
from app.terminal.router import router as terminal_router
from app.yum.router import router as yum_router
from app.terminal.service import terminal_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    logger.info("Argus Server Agent %s starting", __version__)
    yield
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
app.include_router(yum_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}
